"""Persist governance and SDLC agent analyses."""
from alembic import op
import sqlalchemy as sa

revision = "0007_governance_analyses"
down_revision = "0006_requirements_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("requirements_analysis_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("methodology", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirements_analysis_id"], ["requirements_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_governance_analysis_project_version"),
    )
    op.create_index("ix_governance_analyses_project_id", "governance_analyses", ["project_id"])
    op.create_index("ix_governance_analyses_requirements_analysis_id", "governance_analyses", ["requirements_analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_governance_analyses_requirements_analysis_id", table_name="governance_analyses")
    op.drop_index("ix_governance_analyses_project_id", table_name="governance_analyses")
    op.drop_table("governance_analyses")
