"""Chat-related Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class Citation(BaseModel):
    """Schema for source citation."""
    chunk_id: UUID
    content_snippet: str
    page_number: Optional[int] = None
    relevance_score: float


class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session."""
    document_id: UUID
    title: Optional[str] = None
    context_window: int = Field(default=5, ge=1, le=20)
    
    # For multi-document chat (bonus feature)
    additional_document_ids: List[UUID] = []


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    document_id: UUID
    title: Optional[str] = None
    is_active: bool
    document_ids: List[UUID] = []
    context_window: int
    message_count: int
    total_tokens_used: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message."""
    content: str = Field(..., min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    session_id: UUID
    role: str
    content: str
    citations: List[Citation] = []
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_used: Optional[str] = None
    response_time_ms: Optional[int] = None
    confidence_score: Optional[float] = None
    suggested_questions: List[str] = []
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Schema for chat history response."""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]
    total_messages: int


class AskQuestionRequest(BaseModel):
    """Schema for asking a question in a chat session."""
    question: str = Field(..., min_length=1, max_length=4000)
    
    # RAG configuration
    num_context_chunks: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Response customization
    include_citations: bool = True
    include_suggestions: bool = True
    max_response_tokens: int = Field(default=1000, ge=100, le=4000)


class AskQuestionResponse(BaseModel):
    """Schema for question response."""
    message: ChatMessageResponse
    citations: List[Citation] = []
    suggested_questions: List[str] = []
    context_used: int  # Number of chunks used
    response_time_ms: int


class MultiDocumentChatRequest(BaseModel):
    """Schema for multi-document chat (bonus feature)."""
    question: str = Field(..., min_length=1, max_length=4000)
    document_ids: List[UUID] = Field(..., min_length=1, max_length=10)
    num_context_chunks_per_doc: int = Field(default=3, ge=1, le=10)


class MultiDocumentChatResponse(BaseModel):
    """Schema for multi-document chat response."""
    answer: str
    citations: List[Citation] = []
    documents_used: List[UUID] = []
    suggested_questions: List[str] = []
    response_time_ms: int

