"""Dashboard aggregate counts."""
from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    project_count: int
    document_count: int
    embedded_document_count: int
    recommendation_count: int
    conversation_count: int
