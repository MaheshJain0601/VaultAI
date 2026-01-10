"""Pydantic schemas for API validation."""
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentInsightResponse,
    DocumentStatusResponse,
)
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatHistoryResponse,
    AskQuestionRequest,
    AskQuestionResponse,
)
from app.schemas.metrics import (
    DocumentStatsResponse,
    ProcessingMetricsResponse,
    SystemHealthResponse,
)

__all__ = [
    # Document
    "DocumentCreate",
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentUploadResponse",
    "DocumentInsightResponse",
    "DocumentStatusResponse",
    # Chat
    "ChatSessionCreate",
    "ChatSessionResponse",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatHistoryResponse",
    "AskQuestionRequest",
    "AskQuestionResponse",
    # Metrics
    "DocumentStatsResponse",
    "ProcessingMetricsResponse",
    "SystemHealthResponse",
]

