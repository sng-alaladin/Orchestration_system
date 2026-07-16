"""애플리케이션 공통 예외."""


class AppError(Exception):
    """시스템 내부 오류의 공통 베이스."""


class NotInitializedError(AppError):
    """필요한 리소스(DB 등)가 아직 초기화되지 않았다."""
