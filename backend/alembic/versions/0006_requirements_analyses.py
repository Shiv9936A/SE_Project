"""Persist versioned, reviewable requirements analysis results."""
from alembic import op
import sqlalchemy as sa

revision = "0006_requirements_analyses"
down_revision = "0005_adaptive_interviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirements_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirements_analyses_project_id", "requirements_analyses", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_requirements_analyses_project_id", table_name="requirements_analyses")
    op.drop_table("requirements_analyses")
