"""Add nullable vector-search metadata and chunk indexes."""
from alembic import op
import sqlalchemy as sa

revision = "0003_vector_search_metadata"
down_revision = "0002_document_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(length=100), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_status", sa.String(length=30), nullable=True))
    op.add_column("document_chunks", sa.Column("chunk_hash", sa.String(length=64), nullable=True))
    op.add_column("document_chunks", sa.Column("token_count", sa.Integer(), nullable=True))
    # document_id is already indexed by migration 0002.
    op.create_index("ix_document_chunks_chunk_index", "document_chunks", ["chunk_index"])
    op.create_index("ix_document_chunks_chunk_hash", "document_chunks", ["chunk_hash"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_chunk_hash", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_index", table_name="document_chunks")
    op.drop_column("document_chunks", "token_count")
    op.drop_column("document_chunks", "chunk_hash")
    op.drop_column("document_chunks", "embedding_status")
    op.drop_column("document_chunks", "embedding_model")
