"""Persist adaptive project interviews."""
from alembic import op
import sqlalchemy as sa

revision = "0005_adaptive_interviews"
down_revision = "0004_rag_conversations"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("project_idea", sa.Text(), nullable=False),
        sa.Column("business_objective", sa.Text(), nullable=False),
        sa.Column("users_roles", sa.Text(), nullable=False),
        sa.Column("detected_domain", sa.String(length=80), nullable=False),
        sa.Column("asked_questions", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("covered_topics", sa.JSON(), nullable=False),
        sa.Column("uncovered_topics", sa.JSON(), nullable=False),
        sa.Column("current_question", sa.JSON(), nullable=True),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("maximum_questions", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_interview_sessions_project_id"),
    )
    op.create_index("ix_interview_sessions_project_id", "interview_sessions", ["project_id"])

def downgrade() -> None:
    op.drop_index("ix_interview_sessions_project_id", table_name="interview_sessions")
    op.drop_table("interview_sessions")
