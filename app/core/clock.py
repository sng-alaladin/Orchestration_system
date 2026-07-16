"""시각 유틸.

프로젝트 표준: DB에는 timezone 정보 없는 **naive UTC**로 저장한다.
(PostgreSQL과 SQLite(테스트) 양쪽에서 동일하게 동작하도록 하기 위한 규약)
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """naive UTC 현재 시각."""
    return datetime.now(UTC).replace(tzinfo=None)
