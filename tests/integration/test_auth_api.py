"""로그인/세션 API 통합 테스트 (SQLite in-memory)."""

from datetime import timedelta

from httpx import AsyncClient

from app.core.clock import utc_now
from app.core.security import generate_session_token, hash_session_token
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.db.session import SessionFactory
from tests.conftest import TEST_USER_EMAIL, TEST_USER_PASSWORD

COOKIE_NAME = "orch_session"


async def test_login_success_sets_cookie_and_returns_user(
    client: AsyncClient, seeded_user: str
) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": seeded_user, "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_USER_EMAIL
    assert body["display_name"] == "테스트 사용자"
    assert "password" not in response.text
    assert COOKIE_NAME in response.cookies

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


async def test_login_email_is_case_insensitive(client: AsyncClient, seeded_user: str) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": TEST_USER_EMAIL.upper(), "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200


async def test_login_wrong_password_rejected(client: AsyncClient, seeded_user: str) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": seeded_user, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies


async def test_login_unknown_email_rejected_with_same_message(
    client: AsyncClient, seeded_user: str
) -> None:
    wrong_password = await client.post(
        "/api/auth/login",
        json={"email": seeded_user, "password": "wrong-password"},
    )
    unknown_email = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert unknown_email.status_code == 401
    # 계정 존재 여부가 응답 메시지로 드러나지 않아야 한다.
    assert unknown_email.json() == wrong_password.json()


async def test_me_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user_after_login(
    client: AsyncClient, seeded_user: str
) -> None:
    await client.post(
        "/api/auth/login",
        json={"email": seeded_user, "password": TEST_USER_PASSWORD},
    )
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == TEST_USER_EMAIL


async def test_logout_revokes_session(client: AsyncClient, seeded_user: str) -> None:
    await client.post(
        "/api/auth/login",
        json={"email": seeded_user, "password": TEST_USER_PASSWORD},
    )
    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = await client.get("/api/auth/me")
    assert me.status_code == 401


async def test_expired_session_rejected(
    client: AsyncClient, seeded_user: str, session_factory: SessionFactory
) -> None:
    token = generate_session_token()
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(seeded_user)
        assert user is not None
        await SessionRepository(session).create(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=utc_now() - timedelta(minutes=1),
        )
        await session.commit()

    client.cookies.set(COOKIE_NAME, token)
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_garbage_cookie_rejected(client: AsyncClient, seeded_user: str) -> None:
    client.cookies.set(COOKIE_NAME, "garbage-token")
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
