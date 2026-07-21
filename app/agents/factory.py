"""Agent Factory — 검증 체인 + Policy 판정 오케스트레이션 (spec 04 §16).

처리 순서(spec §16):
  정의 → Schema → 권한 → 모델 → MCP 의존성 → Token Budget → Sandbox → Policy 판정 → 등록
Core Agent가 Registry에 직접 쓰지 못하도록, 등록은 이 Factory(코드)만 수행한다.
최종 승인 판정자는 LLM이 아니라 결정론적 Policy Engine이다.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentRegistry
from app.agents.schemas import AgentDefinition
from app.agents.validators import ValidationReport, run_validation_chain
from app.core.enums import AgentLifecycleType, AgentStatus, ProposalType
from app.db.models.agent_definition import AgentDefinitionRecord
from app.policy.engine import PolicyEngine
from app.policy.schemas import ExpansionProposal, PolicyJudgment


@dataclass
class FactoryAssessment:
    """검증 + 정책 판정 결과 (등록 전)."""

    validation: ValidationReport
    proposal: ExpansionProposal | None
    judgment: PolicyJudgment | None

    @property
    def valid(self) -> bool:
        return self.validation.ok


def derive_proposal(defn: AgentDefinition) -> ExpansionProposal:
    """Agent Definition에서 결정론적 위험 신호를 추출한다."""
    perms = defn.permissions
    project_scoped = defn.scope.project_id is not None and defn.lifecycle.type in (
        AgentLifecycleType.PROJECT_SCOPED,
        AgentLifecycleType.TASK_SCOPED,
    )
    permission_escalation = perms.network != "denied" or perms.shell != "denied"
    return ExpansionProposal(
        kind=ProposalType.AGENT,
        name=defn.id,
        reason=defn.purpose,
        project_scoped=project_scoped,
        accesses_secret=perms.accesses_secret,
        admin_privilege=perms.admin,
        permission_escalation=permission_escalation,
        org_wide_registration=defn.lifecycle.type == AgentLifecycleType.PERSISTENT,
    )


class AgentFactory:
    def __init__(self, session: AsyncSession, policy: PolicyEngine | None = None) -> None:
        self._session = session
        self._registry = AgentRegistry(session)
        self._policy = policy or PolicyEngine()

    def assess(
        self, defn: AgentDefinition, *, known_mcp_ids: Iterable[str] = ()
    ) -> FactoryAssessment:
        report = run_validation_chain(defn, known_mcp_ids=known_mcp_ids)
        if not report.ok:
            return FactoryAssessment(validation=report, proposal=None, judgment=None)
        proposal = derive_proposal(defn)
        judgment = self._policy.decide(proposal)
        return FactoryAssessment(validation=report, proposal=proposal, judgment=judgment)

    async def register(
        self,
        defn: AgentDefinition,
        *,
        project_id: uuid.UUID | None,
        status: AgentStatus = AgentStatus.ACTIVE,
    ) -> AgentDefinitionRecord:
        return await self._registry.register(defn, project_id=project_id, status=status)
