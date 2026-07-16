"""Product Definition Agent 입출력 Schema (spec 03 §8~10).

Agent 간에는 이 Schema로 검증된 구조화 결과만 전달한다.
전체 대화 기록·내부 추론은 전달하지 않는다 (spec 07 §27).
"""

from pydantic import BaseModel, Field

from app.core.enums import (
    AutomationClass,
    ClassificationGate,
    DeliverableType,
    RequirementCategory,
    RequirementStatus,
)


class RequirementDraft(BaseModel):
    key: str = Field(pattern=r"^(FR|NFR|BR|EX)-\d{3}$")
    description: str
    status: RequirementStatus
    category: RequirementCategory
    priority: str | None = None  # HIGH / MEDIUM / LOW


class QuestionDraft(BaseModel):
    key: str = Field(pattern=r"^Q-\d{3}$")
    question: str
    reason: str | None = None
    related_requirement_key: str | None = None


class ProjectInput(BaseModel):
    """Core Agent에게 전달되는 입력 (기획안 + 업로드 문서 본문)."""

    project_name: str
    idea_text: str
    document_texts: list[str] = Field(default_factory=list)

    @property
    def combined_text(self) -> str:
        return "\n".join([self.idea_text, *self.document_texts]).strip()


class CoreAnalysis(BaseModel):
    """Core Agent 출력 (spec 03 §8.2)."""

    project_goal: str
    target_users: list[str]
    deliverable_type: DeliverableType
    functional_requirements: list[RequirementDraft]
    open_questions: list[QuestionDraft]
    required_capabilities: list[str]
    expansion_required: bool = False


class ClassificationResult(BaseModel):
    """적합도 분류 게이트 판정 (spec 01 §37)."""

    automation_class: AutomationClass
    gate: ClassificationGate
    reasons: list[str]
    prohibited_features: list[str] = Field(default_factory=list)
    risky_features: list[str] = Field(default_factory=list)
    user_message: str  # 사용자 언어 설명 (차단/축소 사유와 대안)


class RequirementSet(BaseModel):
    """Requirement Agent 출력."""

    requirements: list[RequirementDraft]
    open_questions: list[QuestionDraft]


class BacklogTask(BaseModel):
    key: str
    title: str
    description: str


class UserStory(BaseModel):
    key: str
    title: str
    tasks: list[BacklogTask]


class Epic(BaseModel):
    key: str
    title: str
    stories: list[UserStory]


class SpecificationResult(BaseModel):
    """Specification Agent 출력 (spec 03 §10)."""

    prd_markdown: str
    deliverable_type: DeliverableType
    acceptance_criteria: list[str]
    epics: list[Epic]
    out_of_scope: list[str]
    risks: list[str]
    test_scenarios: list[str]
