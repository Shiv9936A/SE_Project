"""Initial project, questionnaire, documents, and recommendation schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("organization_type", sa.String(length=120), nullable=False),
        sa.Column("team_size", sa.Integer(), nullable=False),
        sa.Column("stakeholders", sa.Text(), nullable=False),
        sa.Column("initial_requirements", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_project_name", "projects", ["project_name"])

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_stability", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("security_criticality", sa.String(length=20), nullable=False),
        sa.Column("compliance_criticality", sa.String(length=20), nullable=False),
        sa.Column("expected_changes", sa.String(length=20), nullable=False),
        sa.Column("continuous_delivery", sa.String(length=3), nullable=False),
        sa.Column("legacy_integration", sa.String(length=3), nullable=False),
        sa.Column("formal_verification", sa.String(length=3), nullable=False),
        sa.Column("stakeholder_availability", sa.String(length=20), nullable=False),
        sa.Column("complexity", sa.String(length=20), nullable=False),
        sa.Column("project_size", sa.String(length=20), nullable=False),
        sa.Column("failure_impact", sa.String(length=20), nullable=False),
        sa.Column("testing_requirement", sa.String(length=20), nullable=False),
        sa.Column("budget_constraint", sa.String(length=20), nullable=False),
        sa.Column("timeline_constraint", sa.String(length=20), nullable=False),
        sa.Column("stakeholder_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_questionnaire_project"),
    )
    op.create_index("ix_questionnaire_responses_project_id", "questionnaire_responses", ["project_id"])

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=100), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_uploaded_documents_project_id", "uploaded_documents", ["project_id"])

    op.create_table(
        "generated_recommendations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommended_sdlc", sa.String(length=100), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("risk_factors", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("scoring_method", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generated_recommendations_project_id", "generated_recommendations", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_recommendations_project_id", table_name="generated_recommendations")
    op.drop_table("generated_recommendations")
    op.drop_index("ix_uploaded_documents_project_id", table_name="uploaded_documents")
    op.drop_table("uploaded_documents")
    op.drop_index("ix_questionnaire_responses_project_id", table_name="questionnaire_responses")
    op.drop_table("questionnaire_responses")
    op.drop_index("ix_projects_project_name", table_name="projects")
    op.drop_table("projects")
