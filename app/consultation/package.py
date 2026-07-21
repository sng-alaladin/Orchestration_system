"""전문가 상담 패키지 빌더 (spec 05 §19.5).

2계층 구조를 강제한다:
  1) 비개발자용 요약 — 사용자가 읽고 이해하는 부분
  2) 개발자용 기술 상세 — 그대로 전달하는 부분 (Secret 마스킹 필수)

패키지에 들어가는 모든 자유 텍스트는 mask_secrets()를 통과한 뒤에만 본문에 삽입된다.
"""

from dataclasses import dataclass, field

from app.consultation.masking import mask_and_merge


@dataclass
class ConsultationOption:
    label: str  # 예: "A. 연결을 허용한다"
    action: str  # 이 선택이 시스템에서 어떤 조치로 이어지는지


@dataclass
class ConsultationQuestion:
    key: str
    question: str
    options: list[ConsultationOption] = field(default_factory=list)


@dataclass
class ConsultationContext:
    project_name: str
    situation_summary: str  # 지금 상황 한 줄 요약
    why_expert_needed: str
    key_questions: list[ConsultationQuestion] = field(default_factory=list)
    # 개발자용 기술 상세
    project_overview: str = ""
    requirements_summary: str = ""
    failure_point: str = ""  # 현재 상태 / Task ID / 오류 메시지 / 로그 요약
    attempts: list[str] = field(default_factory=list)  # 시도한 것과 결과
    config_summary: str = ""
    diff_summary: str = ""
    environment: str = ""


@dataclass
class ConsultationPackage:
    title: str
    markdown: str
    non_developer_summary: str
    questions: list[dict[str, object]]
    masking_summary: dict[str, int]


def build_package(ctx: ConsultationContext) -> ConsultationPackage:
    findings: dict[str, int] = {}

    def m(text: str) -> str:
        return mask_and_merge(text, findings)

    title = f"{m(ctx.project_name)} 개발자 자문 요청"

    # ── 질문 목록 (마스킹) ────────────────────────────────────────
    questions_serialized: list[dict[str, object]] = []
    question_lines: list[str] = []
    for idx, q in enumerate(ctx.key_questions, start=1):
        q_text = m(q.question)
        opts = [
            {"label": m(o.label), "action": m(o.action)} for o in q.options
        ]
        questions_serialized.append(
            {"key": q.key, "question": q_text, "options": opts}
        )
        question_lines.append(f"{idx}. ({q.key}) {q_text}")
        for o in opts:
            question_lines.append(f"   - {o['label']} → {o['action']}")

    # ── 비개발자용 요약 ───────────────────────────────────────────
    nd_lines = [
        "## 비개발자용 요약 (읽고 이해하는 부분)",
        "",
        f"- 지금 상황: {m(ctx.situation_summary)}",
        f"- 왜 개발자 확인이 필요한지: {m(ctx.why_expert_needed)}",
        "- 개발자에게 그대로 전달하면 되는 핵심 질문:",
    ]
    nd_lines.extend(f"  {line}" for line in question_lines)
    non_developer_summary = "\n".join(nd_lines)

    # ── 개발자용 기술 상세 ────────────────────────────────────────
    attempts_block = (
        "\n".join(f"  - {m(a)}" for a in ctx.attempts) if ctx.attempts else "  - (없음)"
    )
    dev_lines = [
        "## 개발자용 기술 상세 (그대로 전달하는 부분)",
        "",
        "### 프로젝트 개요와 관련 요구사항",
        m(ctx.project_overview) or "(요약 없음)",
        "",
        m(ctx.requirements_summary) or "",
        "",
        "### 문제 발생 지점",
        m(ctx.failure_point) or "(해당 없음)",
        "",
        "### 시스템이 시도한 것과 결과",
        attempts_block,
        "",
        "### 관련 설정 / Diff / 실행 환경 (Secret은 마스킹됨)",
        f"- 설정: {m(ctx.config_summary) or '(없음)'}",
        f"- Diff 요약: {m(ctx.diff_summary) or '(없음)'}",
        f"- 실행 환경: {m(ctx.environment) or '(없음)'}",
        "",
        "### 구체적 질문 목록 (선택지로 답변)",
        *question_lines,
    ]
    developer_detail = "\n".join(dev_lines)

    markdown = f"# {title}\n\n{non_developer_summary}\n\n{developer_detail}\n"

    return ConsultationPackage(
        title=title,
        markdown=markdown,
        non_developer_summary=non_developer_summary,
        questions=questions_serialized,
        masking_summary=findings,
    )
