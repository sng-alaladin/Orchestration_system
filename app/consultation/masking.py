"""Secret / 개인정보 마스킹 (spec 05 §19.5, §31).

상담 패키지에 들어가는 모든 자유 텍스트는 저장·노출 전 이 함수를 반드시 통과한다.
"서술이 아니라 테스트로 증명" — tests/unit/test_secret_masking.py 가 심은 값이 남지 않음을 검증한다.

과다 마스킹(정상 텍스트 일부까지 가림)은 허용한다. 과소 마스킹(비밀 노출)은 절대 금지한다.
"""

import re
from dataclasses import dataclass, field

MASK = "***MASKED***"

# ── 값 패턴 (키 이름과 무관하게 값 자체로 식별) ─────────────────────
# 순서 중요: 더 구체적/긴 패턴을 먼저 적용한다.
_VALUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # URL 내 자격증명 user:pass@host → 비밀번호 부분 마스킹
    ("url_credentials", re.compile(r"(?P<scheme>[a-zA-Z][\w+.-]*://[^\s:/@]+:)[^\s@/]+@")),
    # JWT
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")),
    # AWS Access Key ID
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # GitHub 토큰 등 접두 토큰
    ("prefixed_token", re.compile(r"\b(?:gh[pousr]|xox[baprs]|sk|pk|AIza)[-_][A-Za-z0-9]{10,}\b")),
    ("prefixed_token2", re.compile(r"\b(?:ghp|xoxb|xoxp)_[A-Za-z0-9]{10,}\b")),
    # 신용카드 (4-4-4-4, 구분자 -, 공백 허용)
    ("card_number", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # 주민등록번호 (6-7)
    ("kr_rrn", re.compile(r"\b\d{6}[- ]?\d{7}\b")),
    # 한국 휴대폰 번호
    ("kr_phone", re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b")),
    # 이메일
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # 긴 고엔트로피 문자열(해시/키/토큰 후보) — 24자 이상 영숫자/기호 혼합
    ("high_entropy", re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")),
    # 비밀번호/토큰 후보 — 문자와 숫자가 섞인 12자 이상 영숫자 토큰
    # (일반 단어는 숫자가 없어 걸리지 않는다. 과다 마스킹은 허용, 과소 마스킹은 금지)
    (
        "mixed_alnum_secret",
        re.compile(r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{12,}\b"),
    ),
]

# ── 키-값 패턴 (민감 키 이름 → 값 전체 마스킹) ──────────────────────
_SENSITIVE_KEY = (
    r"pass(?:word|wd)?|secret|token|api[_-]?key|apikey|access[_-]?key|secret[_-]?key|"
    r"private[_-]?key|client[_-]?secret|credential|refresh[_-]?token|session[_-]?id|"
    r"authorization|auth[_-]?token|bearer"
)
# 예: password=abc / "api_key": "abc" / Authorization: Bearer abc
_KV_PATTERN = re.compile(
    rf'(?i)(?P<key>"?\b(?:{_SENSITIVE_KEY})\b"?\s*[:=]\s*)(?P<q>"?)(?P<val>[^\s",;]+)',
)
# HTTP Authorization 헤더의 Bearer/Basic 토큰
_BEARER_PATTERN = re.compile(r"(?i)\b(?P<scheme>bearer|basic)\s+(?P<val>[A-Za-z0-9._~+/=-]{6,})")


@dataclass
class MaskingResult:
    text: str
    findings: dict[str, int] = field(default_factory=dict)

    @property
    def masked_any(self) -> bool:
        return bool(self.findings)


def _bump(findings: dict[str, int], kind: str, n: int = 1) -> None:
    if n:
        findings[kind] = findings.get(kind, 0) + n


def mask_secrets(text: str | None) -> MaskingResult:
    """텍스트에서 Secret·개인정보를 마스킹한다. (masked_text, findings)를 반환."""
    if not text:
        return MaskingResult(text=text or "", findings={})

    findings: dict[str, int] = {}
    result = text

    # 1) 민감 키의 값 마스킹 (키 이름은 유지, 값만 가림)
    def _kv_sub(m: re.Match[str]) -> str:
        _bump(findings, "sensitive_kv")
        return f"{m.group('key')}{m.group('q')}{MASK}"

    result = _KV_PATTERN.sub(_kv_sub, result)

    # 2) Authorization: Bearer/Basic 토큰
    def _bearer_sub(m: re.Match[str]) -> str:
        _bump(findings, "auth_header")
        return f"{m.group('scheme')} {MASK}"

    result = _BEARER_PATTERN.sub(_bearer_sub, result)

    # 3) 값 패턴 (키와 무관)
    for kind, pattern in _VALUE_PATTERNS:
        if kind == "url_credentials":

            def _url_sub(m: re.Match[str]) -> str:
                _bump(findings, "url_credentials")
                return f"{m.group('scheme')}{MASK}@"

            result = pattern.sub(_url_sub, result)
            continue

        def _sub(m: re.Match[str], _kind: str = kind) -> str:
            token = m.group(0)
            # 카드 패턴은 하이픈/공백 포함 숫자 시퀀스 — 너무 짧은(구분자만 없는 몇 자리) 오탐 방지
            if _kind == "card_number":
                digits = re.sub(r"\D", "", token)
                if len(digits) < 13:
                    return token
            _bump(findings, _kind)
            return MASK

        result = pattern.sub(_sub, result)

    return MaskingResult(text=result, findings=findings)


def mask_and_merge(text: str | None, findings: dict[str, int]) -> str:
    """마스킹하고 findings 누계를 갱신한 뒤 마스킹된 텍스트를 반환한다."""
    res = mask_secrets(text)
    for kind, n in res.findings.items():
        _bump(findings, kind, n)
    return res.text
