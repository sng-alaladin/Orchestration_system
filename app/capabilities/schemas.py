"""Capability Registry Schema (spec 04 §18)."""

from pydantic import BaseModel, Field

from app.core.enums import ProviderType


class ProviderSpec(BaseModel):
    name: str
    type: ProviderType
    priority: int = 100  # 낮을수록 우선 (기존 자원 재사용 우선)
    status: str = "available"


class CapabilitySpec(BaseModel):
    name: str
    description: str | None = None
    providers: list[ProviderSpec] = Field(default_factory=list)


class MatchedProvider(BaseModel):
    capability: str
    provider_name: str
    provider_type: ProviderType


class GapAnalysisResult(BaseModel):
    required: list[str]
    matched: list[MatchedProvider]
    missing: list[str]

    @property
    def has_gap(self) -> bool:
        return bool(self.missing)
