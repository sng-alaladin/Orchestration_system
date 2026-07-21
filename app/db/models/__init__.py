"""ORM 모델 패키지.

Alembic autogenerate와 metadata.create_all이 전체 모델을 인식하도록
모든 모델을 여기서 import한다.
"""

from app.db.models.agent_definition import AgentDefinitionRecord
from app.db.models.audit_log import AuditLog
from app.db.models.capability import Capability, CapabilityProvider
from app.db.models.expansion_proposal import ExpansionProposalRecord
from app.db.models.expert_consultation import ExpertConsultation
from app.db.models.mcp_server import McpServer, McpTool
from app.db.models.project import Project
from app.db.models.project_classification import ProjectClassification
from app.db.models.project_decision import ProjectDecision
from app.db.models.project_document import ProjectDocument
from app.db.models.project_feedback import ProjectFeedback
from app.db.models.project_requirement import ProjectRequirement, RequirementVersion
from app.db.models.requirement_question import RequirementQuestion
from app.db.models.task import Task
from app.db.models.user import User
from app.db.models.user_approval import UserApproval
from app.db.models.user_session import UserSession
from app.db.models.workflow_checkpoint import WorkflowCheckpoint
from app.db.models.workflow_event import WorkflowEvent

__all__ = [
    "AgentDefinitionRecord",
    "AuditLog",
    "Capability",
    "CapabilityProvider",
    "ExpansionProposalRecord",
    "ExpertConsultation",
    "McpServer",
    "McpTool",
    "Project",
    "ProjectClassification",
    "ProjectDecision",
    "ProjectDocument",
    "ProjectFeedback",
    "ProjectRequirement",
    "RequirementQuestion",
    "RequirementVersion",
    "Task",
    "User",
    "UserApproval",
    "UserSession",
    "WorkflowCheckpoint",
    "WorkflowEvent",
]
