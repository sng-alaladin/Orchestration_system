"""적합도 분류 게이트 단위 테스트 (spec 01 §37, 05 §19.4)."""

from app.core.enums import AutomationClass, ClassificationGate
from app.product.classifier import Classifier


def _classifier() -> Classifier:
    return Classifier()


def test_payment_is_auto_blocked() -> None:
    result = _classifier().classify("고객이 카드결제로 주문하는 쇼핑몰을 만들고 싶다")
    assert result.gate == ClassificationGate.BLOCKED
    assert "결제 기능" in result.prohibited_features
    assert "대안" in result.user_message  # 차단 시 대안을 사용자 언어로 제시


def test_sensitive_personal_data_is_auto_blocked() -> None:
    result = _classifier().classify("직원의 주민등록번호를 저장해서 관리하는 프로그램")
    assert result.gate == ClassificationGate.BLOCKED


def test_production_db_is_auto_blocked() -> None:
    result = _classifier().classify("운영 DB에 직접 접속해서 데이터를 수정하는 도구")
    assert result.gate == ClassificationGate.BLOCKED


def test_plain_project_is_self_service() -> None:
    result = _classifier().classify("엑셀 파일을 입력하면 자동으로 보고서를 만들어주는 프로그램")
    assert result.automation_class == AutomationClass.SELF_SERVICE
    assert result.gate == ClassificationGate.PROCEED


def test_risky_feature_needs_reduced_scope_approval() -> None:
    result = _classifier().classify("경쟁사 사이트를 크롤링해서 가격을 정리해주는 서비스")
    assert result.automation_class == AutomationClass.AI_ASSISTED
    assert result.gate == ClassificationGate.NEEDS_APPROVAL
    assert result.risky_features  # 제외 제안 대상이 명시된다


def test_expert_keywords_need_expert_review() -> None:
    result = _classifier().classify("사내 인증 연동이 필요한 직원용 포털")
    assert result.automation_class == AutomationClass.EXPERT_REVIEW_REQUIRED
    assert result.gate == ClassificationGate.NEEDS_EXPERT


def test_unsupported_project() -> None:
    result = _classifier().classify("모바일 앱스토어 배포까지 해주는 앱을 만들어줘")
    assert result.automation_class == AutomationClass.UNSUPPORTED
    assert result.gate == ClassificationGate.UNSUPPORTED


def test_block_wins_over_other_categories() -> None:
    # 결제 + 크롤링이 함께 있으면 자동 차단이 우선한다
    result = _classifier().classify("크롤링한 상품을 결제까지 되는 사이트로 만들어줘")
    assert result.gate == ClassificationGate.BLOCKED
