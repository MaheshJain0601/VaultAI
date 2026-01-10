"""Document-related database models."""
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, 
    ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class Document(Base):
    """Main document model storing metadata and processing status."""
    
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(SQLEnum(DocumentType), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    file_path = Column(String(512), nullable=False)
    
    # Content metadata
    title = Column(String(500))
    description = Column(Text)
    page_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    
    # Processing status
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_error = Column(Text)
    processing_duration_ms = Column(Integer)
    
    # AI-generated content
    summary = Column(Text)
    key_topics = Column(ARRAY(String), default=[])
    categories = Column(ARRAY(String), default=[])
    sentiment = Column(String(50))
    language = Column(String(50), default="en")
    
    # Embeddings metadata
    embedding_model = Column(String(100))
    chunk_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    insights = relationship("DocumentInsight", back_populates="document", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="document", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_created_at", "created_at"),
        Index("idx_documents_file_type", "file_type"),
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"


class DocumentChunk(Base):
    """Document chunk for RAG - stores text segments with embeddings."""
    
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Chunk content
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    
    # Position metadata
    page_number = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    
    # Embedding (stored as JSON array for simplicity, can use pgvector for production)
    embedding = Column(JSON)  # List of floats
    embedding_model = Column(String(100))
    
    # Token count for context management
    token_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    # Indexes
    __table_args__ = (
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_chunk_index", "chunk_index"),
    )
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"


class DocumentInsight(Base):
    """AI-generated insights about documents."""
    
    __tablename__ = "document_insights"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Insight details
    insight_type = Column(String(50), nullable=False)  # summary, key_points, entities, etc.
    title = Column(String(255))
    content = Column(Text, nullable=False)
    confidence_score = Column(Float)
    
    # Extra data
    extra_data = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="insights")
    
    # Indexes
    __table_args__ = (
        Index("idx_insights_document_id", "document_id"),
        Index("idx_insights_type", "insight_type"),
    )
    
    def __repr__(self):
        return f"<DocumentInsight(id={self.id}, type={self.insight_type})>"

