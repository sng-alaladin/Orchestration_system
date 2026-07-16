"""애플리케이션 설정.

모든 설정은 `ORCH_` 접두 환경변수 또는 `.env` 파일로 주입한다.
코드에 인증정보를 하드코딩하지 않는다 (CLAUDE.md 보안 규칙).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator"
    db_echo: bool = False

    # Agent 실행 모드: "mock"(결정론적) | "live"(Phase 9에서 Codex/ClaudeCode Adapter 연동)
    agent_mode: str = "mock"

    session_cookie_name: str = "orch_session"
    session_ttl_hours: int = 168  # 7일
    session_cookie_secure: bool = False  # 운영(HTTPS)에서는 true

    # 최초 관리자 계정 시드. 미설정 시 시드하지 않는다.
    admin_email: str | None = None
    admin_password: str | None = None
    admin_display_name: str = "관리자"


@lru_cache
def get_settings() -> Settings:
    return Settings()
