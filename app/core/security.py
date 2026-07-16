"""비밀번호 해시와 세션 토큰 유틸.

- 비밀번호: argon2id 해시. 평문·복호화 가능 형태로 저장하지 않는다.
- 세션 토큰: 무작위 불투명 토큰. DB에는 SHA-256 해시만 저장한다
  (DB가 유출되어도 쿠키 토큰을 복원할 수 없다).
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# 존재하지 않는 사용자에 대해서도 동일한 검증 비용을 소모해
# 타이밍으로 계정 존재 여부가 드러나지 않게 한다.
_DUMMY_HASH = _hasher.hash("timing-mitigation-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def spend_dummy_verification() -> None:
    """사용자 부재 시에도 해시 검증 1회 비용을 소모한다."""
    verify_password(_DUMMY_HASH, "wrong-password")


def generate_session_token() -> str:
    """쿠키에 저장되는 불투명 세션 토큰 (256bit)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """DB 저장용 토큰 해시 (SHA-256 hex, 64자)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
