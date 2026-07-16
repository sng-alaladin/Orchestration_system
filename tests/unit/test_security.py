"""비밀번호 해시·세션 토큰 유틸 단위 테스트."""

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    spend_dummy_verification,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret-password")
    assert verify_password(hashed, "secret-password") is True


def test_password_hash_rejects_wrong_password() -> None:
    hashed = hash_password("secret-password")
    assert verify_password(hashed, "wrong-password") is False


def test_password_hash_is_not_plaintext_and_uses_argon2id() -> None:
    hashed = hash_password("secret-password")
    assert "secret-password" not in hashed
    assert hashed.startswith("$argon2id$")


def test_password_hashes_are_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_verify_password_handles_malformed_hash() -> None:
    assert verify_password("not-a-valid-hash", "anything") is False


def test_session_token_is_unique_and_long() -> None:
    tokens = {generate_session_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(token) >= 40 for token in tokens)


def test_session_token_hash_is_deterministic_sha256_hex() -> None:
    token = generate_session_token()
    first = hash_session_token(token)
    assert first == hash_session_token(token)
    assert len(first) == 64
    assert first != token


def test_spend_dummy_verification_does_not_raise() -> None:
    spend_dummy_verification()
