"""Add persistent project analysis runs and nullable analysis links."""
from alembic import op
import sqlalchemy as sa


revision = "0008_analysis_run_history"
down_revision = "0007_governance_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("active_project_id", sa.String(length=36), nullable=True),
        sa.Column("orchestration_version", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("agent_statuses_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('running', 'completed', 'partial', 'failed')", name="ck_analysis_runs_status"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_analysis_runs_project_version"),
        sa.UniqueConstraint("active_project_id", name="uq_analysis_runs_active_project"),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])

    op.add_column("requirements_analyses", sa.Column("analysis_run_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_requirements_analyses_analysis_run_id_analysis_runs",
        "requirements_analyses", "analysis_runs", ["analysis_run_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_requirements_analyses_analysis_run_id", "requirements_analyses", ["analysis_run_id"], unique=True)

    op.add_column("governance_analyses", sa.Column("analysis_run_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_governance_analyses_analysis_run_id_analysis_runs",
        "governance_analyses", "analysis_runs", ["analysis_run_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_governance_analyses_analysis_run_id", "governance_analyses", ["analysis_run_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_governance_analyses_analysis_run_id", table_name="governance_analyses")
    op.drop_constraint("fk_governance_analyses_analysis_run_id_analysis_runs", "governance_analyses", type_="foreignkey")
    op.drop_column("governance_analyses", "analysis_run_id")
    op.drop_index("ix_requirements_analyses_analysis_run_id", table_name="requirements_analyses")
    op.drop_constraint("fk_requirements_analyses_analysis_run_id_analysis_runs", "requirements_analyses", type_="foreignkey")
    op.drop_column("requirements_analyses", "analysis_run_id")
    op.drop_index("ix_analysis_runs_project_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
