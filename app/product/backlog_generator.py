"""Backlog 문서 생성 — Epic / User Story / Development Task (spec 01 §4.1.6)."""

from app.product.schemas import SpecificationResult


def render_backlog_markdown(project_name: str, spec: SpecificationResult) -> str:
    lines: list[str] = [f"# Backlog — {project_name}", ""]
    for epic in spec.epics:
        lines.append(f"## {epic.key} {epic.title}")
        for story in epic.stories:
            lines.append(f"- **{story.key}** {story.title}")
            for task in story.tasks:
                lines.append(f"  - [ ] `{task.key}` {task.title} — {task.description}")
        lines.append("")
    lines.append("## 테스트 시나리오")
    lines += [f"- {scenario}" for scenario in spec.test_scenarios]
    return "\n".join(lines) + "\n"
