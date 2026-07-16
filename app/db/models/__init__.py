"""ORM 모델 패키지.

Alembic autogenerate와 metadata.create_all이 전체 모델을 인식하도록
모든 모델을 여기서 import한다.
"""

from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_decision import ProjectDecision
from app.db.models.project_document import ProjectDocument
from app.db.models.project_feedback import ProjectFeedback
from app.db.models.project_requirement import ProjectRequirement, RequirementVersion
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.db.models.user_session import UserSession

__all__ = [
    "Project",
    "ProjectClassification",
    "ProjectDecision",
    "ProjectDocument",
    "ProjectFeedback",
    "ProjectRequirement",
    "RequirementQuestion",
    "RequirementVersion",
    "User",
    "UserApproval",
    "UserSession",
]
