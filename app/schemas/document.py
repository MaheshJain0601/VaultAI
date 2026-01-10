"""Document-related Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DocumentCreate(BaseModel):
    """Schema for document creation metadata."""
    title: Optional[str] = None
    description: Optional[str] = None


class DocumentInsightResponse(BaseModel):
    """Schema for document insights."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    insight_type: str
    title: Optional[str] = None
    content: str
    confidence_score: Optional[float] = None
    created_at: datetime


class DocumentStatusResponse(BaseModel):
    """Schema for document processing status."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: str
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    processing_duration_ms: Optional[int] = None


class DocumentResponse(BaseModel):
    """Schema for document response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    
    # Content metadata
    title: Optional[str] = None
    description: Optional[str] = None
    page_count: int = 0
    word_count: int = 0
    character_count: int = 0
    
    # Processing status
    status: str
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    processing_duration_ms: Optional[int] = None
    
    # AI-generated content
    summary: Optional[str] = None
    key_topics: List[str] = []
    categories: List[str] = []
    sentiment: Optional[str] = None
    language: str = "en"
    
    # Embeddings info
    embedding_model: Optional[str] = None
    chunk_count: int = 0
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""
    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    message: str = "Document uploaded successfully. Processing started."
    created_at: datetime


class DocumentSummaryRequest(BaseModel):
    """Schema for customizable summary generation."""
    length: str = Field(default="medium", description="short, medium, or long")
    focus_areas: List[str] = Field(default=[], description="Specific topics to focus on")
    tone: str = Field(default="professional", description="professional, casual, or technical")


class DocumentAnalysisResponse(BaseModel):
    """Schema for comprehensive document analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    document_id: UUID
    summary: str
    key_topics: List[str]
    key_points: List[str]
    entities: List[dict]  # Named entities found
    categories: List[str]
    sentiment: str
    sentiment_score: float
    language: str
    reading_time_minutes: int
    complexity_score: float  # 1-10 scale
    insights: List[DocumentInsightResponse]

