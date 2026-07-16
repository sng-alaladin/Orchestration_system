"""설정 로딩 단위 테스트."""

import pytest

from app.core.config import Settings


def test_defaults_do_not_require_env() -> None:
    settings = Settings(_env_file=None)
    assert settings.session_cookie_name == "orch_session"
    assert settings.session_ttl_hours == 168
    assert settings.admin_email is None


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCH_SESSION_TTL_HOURS", "24")
    monkeypatch.setenv("ORCH_ADMIN_EMAIL", "ops@example.com")
    settings = Settings(_env_file=None)
    assert settings.session_ttl_hours == 24
    assert settings.admin_email == "ops@example.com"
