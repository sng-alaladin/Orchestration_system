"""ExpansionService — Proposal 계획 → Policy 판정 → 기록 + 활성화 (spec 04 §16~17, 05 §19).

상태 전환은 하지 않는다(그건 Orchestrator/Workflow 몫). 여기서는:
  - 부족 역량별 Proposal을 만들고 결정론적 Policy Engine으로 판정하고
  - expansion_proposals에 감사 기록으로 남기고
  - 자동 승인분은 실제로 활성화(MCP 상태 승격 + Capability Provider 등록)한다.
집계 결정은 가장 제한적인 판정을 채택한다(차단 > 전문가 > 사용자 > 자동).
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.schemas import CapabilitySpec, ProviderSpec
from app.consultation.package import ConsultationOption, ConsultationQuestion
from app.core.config import Settings
from app.core.enums import (
    AuditEventType,
    ExpansionStatus,
    McpStatus,
    PolicyDecision,
    ProposalType,
    ProviderType,
)
from app.db.models.expansion_proposal import ExpansionProposalRecord
from app.expansion.planner import PlannedProposal, ProposalPlanner
from app.mcp.allowlist import McpAllowlist
from app.mcp.registry import McpRegistry
from app.observability.logging import get_logger
from app.orchestrator.audit import AuditLogger
from app.policy.engine import PolicyEngine
from app.policy.schemas import PolicyJudgment

logger = get_logger(__name__)

# 심각도 순위 (높을수록 제한적) — 집계 결정에 사용
_SEVERITY: dict[PolicyDecision, int] = {
    PolicyDecision.AUTO_APPROVE: 0,
    PolicyDecision.USER_APPROVAL: 1,
    PolicyDecision.EXPERT_REQUIRED: 2,
    PolicyDecision.AUTO_BLOCKED: 3,
}

_STATUS_BY_DECISION: dict[PolicyDecision, ExpansionStatus] = {
    PolicyDecision.AUTO_APPROVE: ExpansionStatus.AUTO_APPROVED,
    PolicyDecision.USER_APPROVAL: ExpansionStatus.PENDING_USER,
    PolicyDecision.EXPERT_REQUIRED: ExpansionStatus.PENDING_EXPERT,
    PolicyDecision.AUTO_BLOCKED: ExpansionStatus.BLOCKED,
}


@dataclass
class JudgedProposal:
    planned: PlannedProposal
    judgment: PolicyJudgment


@dataclass
class ExpansionResolution:
    decision: PolicyDecision
    judged: list[JudgedProposal] = field(default_factory=list)
    reason: str = ""
    alternatives: list[str] = field(default_factory=list)

    def of_decision(self, decision: PolicyDecision) -> list[JudgedProposal]:
        return [j for j in self.judged if j.judgment.decision == decision]


def build_expansion_service(session: AsyncSession, settings: Settings) -> "ExpansionService":
    allowlist = McpAllowlist.load(Path(settings.mcp_allowlist_config))
    planner = ProposalPlanner(
        session,
        allowlist=allowlist,
        catalog_path=Path(settings.expansion_catalog_config),
    )
    return ExpansionService(
        session, planner=planner, mcp_servers_path=Path(settings.mcp_servers_config)
    )


class ExpansionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        planner: ProposalPlanner,
        mcp_servers_path: Path | None = None,
    ) -> None:
        self._session = session
        self._planner = planner
        self._policy = PolicyEngine()
        self._mcp = McpRegistry(session)
        self._audit = AuditLogger(session)
        self._mcp_servers_path = mcp_servers_path

    async def plan_and_judge(
        self, project_id: uuid.UUID, missing: list[str]
    ) -> ExpansionResolution:
        # MCP Registry가 비어 있으면 설정으로 시드 (테스트/최초 기동 대응)
        if self._mcp_servers_path is not None:
            await self._mcp.ensure_seeded(self._mcp_servers_path)
        judged: list[JudgedProposal] = []
        for capability in missing:
            planned = await self._planner.plan(capability)
            judgment = self._policy.decide(planned.proposal)
            await self._persist(project_id, planned, judgment)
            judged.append(JudgedProposal(planned=planned, judgment=judgment))

        decision = self._aggregate([j.judgment.decision for j in judged])
        reason, alternatives = self._summarize(decision, judged)
        return ExpansionResolution(
            decision=decision, judged=judged, reason=reason, alternatives=alternatives
        )

    async def activate(self, resolution: ExpansionResolution) -> list[str]:
        """자동 승인된 Proposal을 실제로 활성화한다. 반환: 활성화된 capability 목록."""
        activated: list[str] = []
        for jp in resolution.of_decision(PolicyDecision.AUTO_APPROVE):
            if jp.planned.strategy == "MCP_CONNECTION" and jp.planned.server_id:
                await self._mcp.set_status(jp.planned.server_id, McpStatus.APPROVED)
                await self._register_provider(
                    jp.planned.capability, jp.planned.server_id, ProviderType.MCP
                )
                activated.append(jp.planned.capability)
        return activated

    async def approve_pending(self, project_id: uuid.UUID) -> list[str]:
        """대기(PENDING_USER/PENDING_EXPERT) 확장을 승인·활성화한다.

        사용자 승인 또는 전문가 확인 완료 후 호출된다. 반환: 활성화된 capability 목록.
        """
        from sqlalchemy import select

        stmt = select(ExpansionProposalRecord).where(
            ExpansionProposalRecord.project_id == project_id,
            ExpansionProposalRecord.status.in_(
                [ExpansionStatus.PENDING_USER, ExpansionStatus.PENDING_EXPERT]
            ),
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        activated: list[str] = []
        for row in rows:
            # row.name = 해결 대상 capability, signals["name"] = 대상 서버 id
            server_id = str(row.signals.get("name", "")) if row.signals else ""
            if row.kind == ProposalType.MCP_CONNECTION and server_id:
                await self._mcp.set_status(server_id, McpStatus.APPROVED)
                await self._register_provider(row.name, server_id, ProviderType.MCP)
                activated.append(row.name)
            row.status = ExpansionStatus.APPROVED
        await self._session.flush()
        return activated

    def build_expert_questions(
        self, resolution: ExpansionResolution
    ) -> list[ConsultationQuestion]:
        questions: list[ConsultationQuestion] = []
        for jp in resolution.of_decision(PolicyDecision.EXPERT_REQUIRED):
            cap = jp.planned.capability
            target = jp.planned.server_id or cap
            questions.append(
                ConsultationQuestion(
                    key=f"EXP-{cap}",
                    question=(
                        f"'{cap}' 기능을 위해 '{target}' 연결이 필요합니다. 어떻게 할까요?"
                    ),
                    options=[
                        ConsultationOption(
                            label="A. 연결을 허용한다 (개발자가 안전한 연결을 확인함)",
                            action="자문 화면에서 A 선택 → 게이트를 해제하고 확장을 진행합니다.",
                        ),
                        ConsultationOption(
                            label="B. 이 기능을 제외하고 진행한다",
                            action="자문 화면에서 B 선택 → 해당 기능을 빼고 요구사항을 다시 정리",
                        ),
                        ConsultationOption(
                            label="C. 중단한다",
                            action="자문 화면에서 C 선택 → 프로젝트를 중단합니다.",
                        ),
                    ],
                )
            )
        return questions

    # ── 내부 ────────────────────────────────────────────────────────

    async def _persist(
        self, project_id: uuid.UUID, planned: PlannedProposal, judgment: PolicyJudgment
    ) -> None:
        self._session.add(
            ExpansionProposalRecord(
                project_id=project_id,
                kind=planned.proposal.kind,
                # name = 해결 대상 capability (대상 서버·Agent 이름은 signals에 보존)
                name=planned.capability,
                reason=planned.proposal.reason,
                decision=judgment.decision,
                matched_rule=judgment.matched_rule,
                policy_reason=judgment.reason,
                alternatives=list(judgment.alternatives),
                signals=planned.proposal.model_dump(mode="json"),
                status=_STATUS_BY_DECISION[judgment.decision],
            )
        )
        await self._session.flush()
        await self._audit.record(
            event_type=AuditEventType.POLICY_DECISION,
            subject_type="project",
            subject_id=project_id,
            reason=f"{planned.proposal.name}: {judgment.decision} ({judgment.matched_rule})",
        )

    async def _register_provider(
        self, capability: str, provider_name: str, provider_type: ProviderType
    ) -> None:
        from app.capabilities.registry import CapabilityRegistry

        await CapabilityRegistry(self._session).upsert(
            CapabilitySpec(
                name=capability,
                providers=[ProviderSpec(name=provider_name, type=provider_type, priority=50)],
            )
        )

    def _aggregate(self, decisions: list[PolicyDecision]) -> PolicyDecision:
        if not decisions:
            # 부족 역량이 없으면 확장이 필요 없음 → 자동 승인으로 취급 (진행)
            return PolicyDecision.AUTO_APPROVE
        return max(decisions, key=lambda d: _SEVERITY[d])

    def _summarize(
        self, decision: PolicyDecision, judged: list[JudgedProposal]
    ) -> tuple[str, list[str]]:
        relevant = [j for j in judged if j.judgment.decision == decision]
        caps = ", ".join(j.planned.capability for j in relevant)
        reasons = " / ".join(dict.fromkeys(j.judgment.reason for j in relevant))
        alternatives: list[str] = []
        for j in relevant:
            for alt in j.judgment.alternatives:
                if alt not in alternatives:
                    alternatives.append(alt)

        if decision == PolicyDecision.AUTO_BLOCKED:
            return (f"다음 확장은 자동으로 진행할 수 없습니다: {caps}\n{reasons}", alternatives)
        if decision == PolicyDecision.EXPERT_REQUIRED:
            return (
                f"다음 기능은 진행 전 개발자 확인이 필요합니다: {caps}\n{reasons}\n"
                "개발자에게 전달할 상담 자료를 생성했습니다.",
                alternatives,
            )
        if decision == PolicyDecision.USER_APPROVAL:
            return (
                f"다음 확장에 대한 승인이 필요합니다: {caps}\n{reasons}",
                alternatives,
            )
        return (f"필요한 확장을 자동으로 준비했습니다: {caps}" if caps else "", alternatives)
