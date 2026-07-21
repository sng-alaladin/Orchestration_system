"""Agent Definition 스키마 (spec 04 §15.3).

Core Agent가 생성하는 Agent Definition의 구조를 Pydantic으로 강제한다.
검증(validators)·정책 판정(Policy Engine)을 통과해야만 Registry에 등록된다.
"""

import re

from pydantic import BaseModel, Field, field_validator

from app.core.enums import AgentLifecycleType

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# MVP에서 사용 가능한 모델 Provider (Adapter는 Phase 9에서 실제 연동)
ALLOWED_MODEL_PROVIDERS = frozenset({"mock", "claude-code", "codex"})

# 권한 필드 허용 값
FILESYSTEM_LEVELS = frozenset({"denied", "read_only", "read_write_scoped"})
NETWORK_LEVELS = frozenset({"denied", "allowlisted"})
SHELL_LEVELS = frozenset({"denied", "allowlisted"})


class AgentModelRef(BaseModel):
    provider: str
    adapter: str


class AgentScope(BaseModel):
    project_id: str | None = None
    allowed_paths: list[str] = Field(default_factory=list)


class AgentPermissions(BaseModel):
    filesystem: str = "read_only"
    network: str = "denied"
    shell: str = "denied"
    # 관리자 권한은 정의상 항상 거부되어야 한다 (spec 05 §31). 기본 false.
    admin: bool = False
    # Secret 접근 요구 여부 (검증에서 차단 대상)
    accesses_secret: bool = False


class AgentTokenBudget(BaseModel):
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)


class AgentLifecycle(BaseModel):
    type: AgentLifecycleType = AgentLifecycleType.PROJECT_SCOPED
    expires_after_project: bool = True


class AgentDefinition(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    purpose: str = Field(min_length=1)
    model: AgentModelRef
    scope: AgentScope = Field(default_factory=AgentScope)
    capabilities: list[str] = Field(default_factory=list)
    mcp_dependencies: list[str] = Field(default_factory=list)
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    rules: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)
    token_budget: AgentTokenBudget
    lifecycle: AgentLifecycle = Field(default_factory=AgentLifecycle)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _ID_PATTERN.match(value):
            raise ValueError(
                "Agent id는 소문자·숫자·하이픈(kebab-case)만 허용합니다 (2~64자)."
            )
        return value

    @field_validator("version")
    @classmethod
    def _valid_version(cls, value: str) -> str:
        if not _SEMVER_PATTERN.match(value):
            raise ValueError("version은 X.Y.Z 형식이어야 합니다.")
        return value
