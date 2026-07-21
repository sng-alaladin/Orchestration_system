"""Secret / 개인정보 마스킹 테스트 (spec 05 §19.5 — "서술이 아니라 테스트로 증명").

인증정보·개인정보를 실제로 심은 입력으로 상담 패키지를 만들었을 때
그 원본 값이 출력(패키지 본문·질문·저장 필드)에 남지 않는지 검증한다.
"""

from app.consultation.masking import MASK, mask_secrets
from app.consultation.package import (
    ConsultationContext,
    ConsultationOption,
    ConsultationQuestion,
    build_package,
)

# 심어 둘 비밀·개인정보 원본 값 (출력에 절대 남으면 안 된다)
SECRETS = {
    "password": "hunter2SuperSecret",
    "api_key_value": "sk-live-ABCDEF0123456789abcdef0123",
    "aws_key": "AKIAIOSFODNN7EXAMPLE",
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.dQw4w9WgXcQabcdEFGh",
    "bearer": "Bearer abcdef1234567890TOKENVALUE",
    "email": "hong.gildong@example.com",
    "phone": "010-1234-5678",
    "rrn": "900101-1234567",
    "card": "4111-1111-1111-1111",
    "db_url_pw": "postgresql://admin:MyDbP4ss@10.0.0.5/prod",
}


def _all_raw_values() -> list[str]:
    values = [
        "hunter2SuperSecret",
        "sk-live-ABCDEF0123456789abcdef0123",
        "AKIAIOSFODNN7EXAMPLE",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.dQw4w9WgXcQabcdEFGh",
        "abcdef1234567890TOKENVALUE",
        "hong.gildong@example.com",
        "010-1234-5678",
        "900101-1234567",
        "4111-1111-1111-1111",
        "MyDbP4ss",  # DB URL 내 비밀번호
    ]
    return values


def test_mask_secrets_detects_and_removes_each_kind() -> None:
    for label, raw in SECRETS.items():
        text = f"{label}={raw}"
        result = mask_secrets(text)
        assert raw not in result.text, f"{label} 원본이 남았습니다: {result.text}"
        assert result.masked_any, f"{label} 마스킹이 감지되지 않았습니다"


def test_consultation_package_contains_no_planted_secrets() -> None:
    """비밀·개인정보를 모든 자유 텍스트 필드에 심고 패키지를 만들어도 원본이 남지 않는다."""
    blob = "\n".join(f"{k}={v}" for k, v in SECRETS.items())
    context = ConsultationContext(
        project_name="정산 자동화",
        situation_summary=f"로그인 정보: {SECRETS['password']}, 담당자 {SECRETS['email']}",
        why_expert_needed=f"외부 연동에 API 키 {SECRETS['api_key_value']} 가 필요합니다.",
        key_questions=[
            ConsultationQuestion(
                key="Q1",
                question=f"AWS 키 {SECRETS['aws_key']} 로 연결할까요?",
                options=[
                    ConsultationOption(
                        label=f"A. 토큰 {SECRETS['bearer']} 사용",
                        action=f"DB {SECRETS['db_url_pw']} 에 연결",
                    )
                ],
            )
        ],
        project_overview=blob,
        requirements_summary=f"주민번호 {SECRETS['rrn']}, 카드 {SECRETS['card']} 저장",
        failure_point=f"JWT {SECRETS['jwt']} 검증 실패, 연락처 {SECRETS['phone']}",
        attempts=[f"토큰 재발급: {SECRETS['bearer']}"],
        config_summary=f"password={SECRETS['password']}",
        diff_summary=f"api_key={SECRETS['api_key_value']}",
        environment=f"DATABASE_URL={SECRETS['db_url_pw']}",
    )
    package = build_package(context)

    # 패키지가 노출하는 모든 텍스트를 한 덩어리로 모아 검사
    haystack = package.markdown + package.non_developer_summary
    for q in package.questions:
        haystack += str(q)

    for raw in _all_raw_values():
        assert raw not in haystack, f"상담 패키지에 원본 비밀이 남았습니다: {raw!r}"

    # 실제로 무언가 마스킹되었고, 마스크 토큰이 본문에 존재한다
    assert package.masking_summary, "마스킹 요약이 비어 있습니다"
    assert MASK in package.markdown

    # 2계층 구조는 유지된다
    assert "비개발자용 요약" in package.markdown
    assert "개발자용 기술 상세" in package.markdown


def test_masking_preserves_non_secret_text() -> None:
    result = mask_secrets("이 프로젝트는 판매 보고서를 이메일로 공유합니다.")
    # 일반 한국어 문장은 그대로 유지 (이메일 '주소'가 아니면 마스킹하지 않음)
    assert "판매 보고서" in result.text
