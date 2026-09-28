"""Add extracted page counts and persisted document chunks."""
from alembic import op
import sqlalchemy as sa

revision = "0002_document_chunks"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("uploaded_documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["uploaded_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("uploaded_documents", "page_count")
