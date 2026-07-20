"""상태 머신 엔진 — 선언적 전환 테이블 + Guard + 체크포인트 + Idempotency + Audit.

- 상태 변경은 이 엔진의 fire()로만 수행한다. LLM이 직접 상태를 변경하지 않는다.
- 테이블에 없는 전환은 불법 전환으로 거부하고 Audit Log에 기록한다.
- 예외 상태 진입 시 직전 상태를 체크포인트로 저장하고,
  CHECKPOINT 목적지는 최신 체크포인트의 상태로 해석한다.
- 동일 idempotency_key 이벤트는 한 번만 적용한다.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditEventType
from app.core.exceptions import AppError
from app.db.models.workflow_event import WorkflowEvent
from app.orchestrator.audit import AuditLogger
from app.orchestrator.checkpoints import CheckpointStore
from app.orchestrator.transition_guard import GuardRegistry
from app.orchestrator.transitions import CHECKPOINT, MachineType, TransitionDef


class StateMachineError(AppError):
    """상태 머신 공통 오류 — 사용자 언어 메시지를 담는다."""


class IllegalTransitionError(StateMachineError):
    pass


class GuardRejectedError(StateMachineError):
    pass


class StateSubject(Protocol):
    id: uuid.UUID
    status: str


@dataclass(frozen=True)
class TransitionResult:
    subject_id: uuid.UUID
    machine: MachineType
    event: str
    from_state: str
    to_state: str
    applied: bool
    idempotent_replay: bool = False


class StateMachine:
    def __init__(
        self,
        *,
        session: AsyncSession,
        machine: MachineType,
        subject_type: str,
        transitions: tuple[TransitionDef, ...],
        guards: GuardRegistry,
        exception_states: frozenset[str],
        max_retries: int = 3,
    ) -> None:
        self._session = session
        self._machine = machine
        self._subject_type = subject_type
        self._guards = guards
        self._exception_states = exception_states
        self._max_retries = max_retries
        self._audit = AuditLogger(session)
        self._checkpoints = CheckpointStore(session)

        self._index: dict[tuple[str, str], TransitionDef] = {}
        for t in transitions:
            key = (t.source, t.event)
            if key in self._index:
                raise ValueError(f"중복 전환 정의: {key}")
            self._index[key] = t

    @property
    def checkpoints(self) -> CheckpointStore:
        return self._checkpoints

    async def fire(
        self,
        subject: StateSubject,
        event: str,
        *,
        reason: str | None = None,
        actor_type: str = "system",
        actor_id: uuid.UUID | None = None,
        context: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        checkpoint_payload: dict[str, Any] | None = None,
    ) -> TransitionResult:
        ctx: dict[str, Any] = dict(context or {})
        ctx["_subject_type"] = self._subject_type
        ctx["_max_retries"] = self._max_retries

        # 1) Idempotency: 동일 key의 이벤트는 한 번만 적용
        if idempotency_key is not None:
            stmt = select(WorkflowEvent).where(
                WorkflowEvent.idempotency_key == idempotency_key
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                await self._audit.record(
                    event_type=AuditEventType.IDEMPOTENT_REPLAY,
                    subject_type=self._subject_type,
                    subject_id=subject.id,
                    machine=self._machine,
                    event=event,
                    from_state=existing.from_state,
                    to_state=existing.to_state,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    reason=f"idempotency_key={idempotency_key} 중복 — 재적용 생략",
                )
                return TransitionResult(
                    subject_id=subject.id,
                    machine=self._machine,
                    event=event,
                    from_state=existing.from_state,
                    to_state=existing.to_state,
                    applied=False,
                    idempotent_replay=True,
                )

        from_state = subject.status

        # 2) 전환 정의 조회 — 테이블에 없으면 불법 전환
        tdef = self._index.get((from_state, event))
        if tdef is None:
            await self._audit.record(
                event_type=AuditEventType.TRANSITION_REJECTED,
                subject_type=self._subject_type,
                subject_id=subject.id,
                machine=self._machine,
                event=event,
                from_state=from_state,
                actor_type=actor_type,
                actor_id=actor_id,
                reason="전환 테이블에 없는 불법 전환",
            )
            raise IllegalTransitionError(
                f"불법 상태 전이: {self._machine} {from_state} --{event}--> (정의 없음)"
            )

        # 3) CHECKPOINT 목적지 해석
        target = tdef.target
        if target == CHECKPOINT:
            checkpoint = await self._checkpoints.latest(self._subject_type, subject.id)
            if checkpoint is None:
                await self._audit.record(
                    event_type=AuditEventType.GUARD_REJECTED,
                    subject_type=self._subject_type,
                    subject_id=subject.id,
                    machine=self._machine,
                    event=event,
                    from_state=from_state,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    reason="복귀할 체크포인트가 없음",
                )
                raise GuardRejectedError("복귀할 체크포인트가 없습니다.")
            target = checkpoint.state

        # 4) Guard 평가
        if tdef.guard is not None:
            result = await self._guards.evaluate(tdef.guard, self._session, subject, ctx)
            if not result.ok:
                await self._audit.record(
                    event_type=AuditEventType.GUARD_REJECTED,
                    subject_type=self._subject_type,
                    subject_id=subject.id,
                    machine=self._machine,
                    event=event,
                    from_state=from_state,
                    to_state=target,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    reason=f"Guard '{tdef.guard}' 거부: {result.reason}",
                )
                raise GuardRejectedError(result.reason or f"Guard 거부: {tdef.guard}")

        # 5) 예외 상태 진입 시 직전 상태 체크포인트 저장
        if target in self._exception_states and from_state not in self._exception_states:
            await self._checkpoints.save(
                self._subject_type, subject.id, state=from_state,
                payload=checkpoint_payload or {},
            )

        # 6) 상태 적용 + 이벤트·감사 기록
        subject.status = target
        if hasattr(subject, "status_reason"):
            subject.status_reason = reason
        self._session.add(
            WorkflowEvent(
                subject_type=self._subject_type,
                subject_id=subject.id,
                machine=self._machine,
                event=event,
                from_state=from_state,
                to_state=target,
                idempotency_key=idempotency_key,
            )
        )
        await self._audit.record(
            event_type=AuditEventType.STATE_TRANSITION,
            subject_type=self._subject_type,
            subject_id=subject.id,
            machine=self._machine,
            event=event,
            from_state=from_state,
            to_state=target,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        )
        await self._session.flush()
        return TransitionResult(
            subject_id=subject.id,
            machine=self._machine,
            event=event,
            from_state=from_state,
            to_state=target,
            applied=True,
        )
