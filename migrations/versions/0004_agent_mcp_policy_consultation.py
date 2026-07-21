"""Agent Registry + MCP Registry + 확장 Proposal + 전문가 상담 테이블 (Phase 6~7)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lifecycle_type", sa.String(length=20), nullable=False),
        sa.Column("expires_after_project", sa.Boolean(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "project_id", name="uq_agent_definition_scope"),
    )
    op.create_index("ix_agent_definitions_agent_id", "agent_definitions", ["agent_id"])
    op.create_index("ix_agent_definitions_project_id", "agent_definitions", ["project_id"])

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("server_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=10), nullable=False),
        sa.Column("data_classification", sa.String(length=20), nullable=False),
        sa.Column("external_network", sa.Boolean(), nullable=False),
        sa.Column("read_permissions", sa.JSON(), nullable=False),
        sa.Column("write_permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_servers_server_id", "mcp_servers", ["server_id"], unique=True)

    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("server_pk", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("write", sa.Boolean(), nullable=False),
        sa.Column("requires_user_approval", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["server_pk"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_pk", "name", name="uq_mcp_tool"),
    )
    op.create_index("ix_mcp_tools_server_pk", "mcp_tools", ["server_pk"])

    op.create_table(
        "expansion_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("matched_rule", sa.String(length=60), nullable=False),
        sa.Column("policy_reason", sa.Text(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expansion_proposals_project_id", "expansion_proposals", ["project_id"]
    )

    op.create_table(
        "expert_consultations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("package_markdown", sa.Text(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("masking_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expert_consultations_project_id", "expert_consultations", ["project_id"]
    )


def downgrade() -> None:
    for table in (
        "expert_consultations",
        "expansion_proposals",
        "mcp_tools",
        "mcp_servers",
        "agent_definitions",
    ):
        op.drop_table(table)
