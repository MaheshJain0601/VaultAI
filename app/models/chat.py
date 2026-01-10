"""Chat-related database models."""
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime,
    ForeignKey, JSON, Enum as SQLEnum, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class MessageRole(str, Enum):
    """Chat message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(Base):
    """Chat session for document Q&A."""
    
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Session metadata
    title = Column(String(255))
    is_active = Column(Boolean, default=True)
    
    # Multi-document support (optional - for bonus feature)
    document_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])
    
    # Context configuration
    context_window = Column(Integer, default=5)  # Number of previous messages to include
    
    # Statistics
    message_count = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime)
    
    # Relationships
    document = relationship("Document", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    
    # Indexes
    __table_args__ = (
        Index("idx_sessions_document_id", "document_id"),
        Index("idx_sessions_created_at", "created_at"),
        Index("idx_sessions_is_active", "is_active"),
    )
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, document_id={self.document_id})>"


class ChatMessage(Base):
    """Individual chat message with citations."""
    
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Message content
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    
    # For assistant messages - source citations
    citations = Column(JSON, default=[])  # List of {chunk_id, content_snippet, page_number, relevance_score}
    
    # Context used for this response
    context_chunks = Column(JSON, default=[])  # Chunk IDs used for context
    
    # Token usage
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Response metadata
    model_used = Column(String(100))
    response_time_ms = Column(Integer)
    confidence_score = Column(Float)
    
    # Follow-up suggestions (bonus feature)
    suggested_questions = Column(ARRAY(String), default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_role", "role"),
    )
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role})>"

