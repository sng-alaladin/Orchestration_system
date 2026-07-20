"""Development 상태 머신 (tasks 대상)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.state_machine import StateMachine
from app.orchestrator.transition_guard import GuardRegistry
from app.orchestrator.transitions import (
    DEVELOPMENT_EXCEPTION_STATES,
    DEVELOPMENT_TRANSITIONS,
    MachineType,
)

DEVELOPMENT_SUBJECT_TYPE = "task"


def build_development_state_machine(
    session: AsyncSession, *, max_retries: int = 3, guards: GuardRegistry | None = None
) -> StateMachine:
    return StateMachine(
        session=session,
        machine=MachineType.DEVELOPMENT,
        subject_type=DEVELOPMENT_SUBJECT_TYPE,
        transitions=DEVELOPMENT_TRANSITIONS,
        guards=guards or GuardRegistry(),
        exception_states=DEVELOPMENT_EXCEPTION_STATES,
        max_retries=max_retries,
    )
