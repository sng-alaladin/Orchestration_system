"""Capability Gap 분석 (spec 04 §15.1) — 요구 역량 대비 부족분을 판정한다."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.matcher import CapabilityMatcher
from app.capabilities.schemas import GapAnalysisResult, MatchedProvider
from app.observability.logging import get_logger

logger = get_logger(__name__)


class GapAnalyzer:
    def __init__(self, session: AsyncSession) -> None:
        self._matcher = CapabilityMatcher(session)

    async def analyze(self, required: list[str]) -> GapAnalysisResult:
        matches = await self._matcher.match(required)
        matched: list[MatchedProvider] = [m for m in matches.values() if m is not None]
        missing = sorted(name for name, m in matches.items() if m is None)
        result = GapAnalysisResult(required=required, matched=matched, missing=missing)
        logger.info(
            "capability_gap_analyzed",
            required=required,
            missing=missing,
            matched=[f"{m.capability}→{m.provider_name}" for m in matched],
        )
        return result
