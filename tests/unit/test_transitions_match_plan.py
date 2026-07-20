"""transitions.py ↔ IMPLEMENTATION_PLAN.md §6.1~6.4 완전 대조 테스트.

테이블에만 있고 코드에 없는 전환, 코드에만 있고 테이블에 없는 전환이
모두 0이어야 한다 (세션 3 추가 지시 2).
"""

import re
from pathlib import Path

from app.orchestrator.transition_guard import GuardRegistry
from app.orchestrator.transitions import (
    DEVELOPMENT_TRANSITIONS,
    PRODUCT_TRANSITIONS,
    TransitionDef,
)

PLAN_PATH = Path(__file__).resolve().parents[2] / "IMPLEMENTATION_PLAN.md"

_STATE_TOKEN = re.compile(r"^[A-Z][A-Z_]*$")
_CHECKPOINT_CELL = "직전 상태 (체크포인트)"
_TERMINAL_EVENT = "(터미널)"


def _section(text: str, start_marker: str, end_markers: list[str]) -> str:
    start = text.index(start_marker)
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + len(start_marker))
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def _parse_rows(section: str) -> set[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        source_cell, event, target = cells[0], cells[1], cells[2]
        # 헤더/구분선 행 제외
        if source_cell in ("현재 상태", "예외 상태") or set(source_cell) <= {"-"}:
            continue
        if event == _TERMINAL_EVENT:
            continue  # 터미널 상태 — 전환 없음
        if target == _CHECKPOINT_CELL:
            target = "CHECKPOINT"
        assert _STATE_TOKEN.match(event), f"이벤트 토큰 형식 오류: {event!r}"
        assert _STATE_TOKEN.match(target), f"목적지 토큰 형식 오류: {target!r}"
        # 다중 소스 행 (· 구분) 전개
        for source in (s.strip() for s in source_cell.split("·")):
            assert _STATE_TOKEN.match(source), f"소스 토큰 형식 오류: {source!r}"
            rows.add((source, event, target))
    assert rows, "테이블에서 전환을 하나도 파싱하지 못했다"
    return rows


def _plan_tables() -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    text = PLAN_PATH.read_text(encoding="utf-8")
    product = _parse_rows(_section(text, "### 6.1", ["### 6.2"])) | _parse_rows(
        _section(text, "### 6.3", ["### 6.4"])
    )
    development = _parse_rows(_section(text, "### 6.2", ["### 6.3"])) | _parse_rows(
        _section(text, "### 6.4", ["공통 규칙:"])
    )
    return product, development


def _code_set(transitions: tuple[TransitionDef, ...]) -> set[tuple[str, str, str]]:
    return {(t.source, t.event, t.target) for t in transitions}


def _assert_exact_match(
    plan: set[tuple[str, str, str]], code: set[tuple[str, str, str]], machine: str
) -> None:
    only_in_plan = sorted(plan - code)
    only_in_code = sorted(code - plan)
    assert not only_in_plan and not only_in_code, (
        f"[{machine}] 전환 테이블 불일치\n"
        f"  테이블에만 있음 ({len(only_in_plan)}): {only_in_plan}\n"
        f"  코드에만 있음 ({len(only_in_code)}): {only_in_code}"
    )


def test_product_transitions_match_plan_exactly() -> None:
    plan_product, _ = _plan_tables()
    _assert_exact_match(plan_product, _code_set(PRODUCT_TRANSITIONS), "PRODUCT")


def test_development_transitions_match_plan_exactly() -> None:
    _, plan_dev = _plan_tables()
    _assert_exact_match(plan_dev, _code_set(DEVELOPMENT_TRANSITIONS), "DEVELOPMENT")


def test_no_duplicate_source_event_pairs() -> None:
    for name, transitions in (
        ("PRODUCT", PRODUCT_TRANSITIONS),
        ("DEVELOPMENT", DEVELOPMENT_TRANSITIONS),
    ):
        keys = [(t.source, t.event) for t in transitions]
        assert len(keys) == len(set(keys)), f"[{name}] (source, event) 중복 정의 존재"


def test_terminal_states_have_no_outgoing_transitions() -> None:
    product_sources = {t.source for t in PRODUCT_TRANSITIONS}
    dev_sources = {t.source for t in DEVELOPMENT_TRANSITIONS}
    assert "CANCELLED" not in product_sources
    assert "CANCELLED" not in dev_sources
    assert "COMPLETED" not in dev_sources


def test_all_guard_names_are_resolvable() -> None:
    known = GuardRegistry().known_names()
    for transitions in (PRODUCT_TRANSITIONS, DEVELOPMENT_TRANSITIONS):
        for t in transitions:
            if t.guard is None or t.guard.startswith("deferred:"):
                continue
            assert t.guard in known, (
                f"GuardRegistry에 없는 Guard: {t.guard} ({t.source}--{t.event})"
            )
