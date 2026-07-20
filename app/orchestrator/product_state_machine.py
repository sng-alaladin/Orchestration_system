"""Product Definition 상태 머신 (projects 대상)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.state_machine import StateMachine
from app.orchestrator.transition_guard import GuardRegistry
from app.orchestrator.transitions import (
    PRODUCT_EXCEPTION_STATES,
    PRODUCT_TRANSITIONS,
    MachineType,
)

PRODUCT_SUBJECT_TYPE = "project"


def build_product_state_machine(
    session: AsyncSession, *, max_retries: int = 3, guards: GuardRegistry | None = None
) -> StateMachine:
    return StateMachine(
        session=session,
        machine=MachineType.PRODUCT,
        subject_type=PRODUCT_SUBJECT_TYPE,
        transitions=PRODUCT_TRANSITIONS,
        guards=guards or GuardRegistry(),
        exception_states=PRODUCT_EXCEPTION_STATES,
        max_retries=max_retries,
    )
