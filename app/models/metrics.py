"""Metrics and monitoring database models."""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime,
    JSON, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MetricType(str, Enum):
    """Types of processing metrics."""
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_PROCESSING = "document_processing"
    TEXT_EXTRACTION = "text_extraction"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    AI_ANALYSIS = "ai_analysis"
    CHAT_QUERY = "chat_query"
    RETRIEVAL = "retrieval"


class ProcessingMetric(Base):
    """Metrics for document processing operations."""
    
    __tablename__ = "processing_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    document_id = Column(UUID(as_uuid=True), index=True)
    session_id = Column(UUID(as_uuid=True), index=True)
    
    # Metric details
    metric_type = Column(SQLEnum(MetricType), nullable=False)
    operation_name = Column(String(100), nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # Status
    success = Column(Integer, default=1)  # 1 for success, 0 for failure
    error_message = Column(Text)
    
    # Resource usage
    tokens_used = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    
    # Additional data
    extra_data = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_metrics_type", "metric_type"),
        Index("idx_metrics_created_at", "created_at"),
        Index("idx_metrics_success", "success"),
    )
    
    def __repr__(self):
        return f"<ProcessingMetric(id={self.id}, type={self.metric_type})>"


class SystemMetric(Base):
    """System-level performance metrics."""
    
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False)
    metric_category = Column(String(50), nullable=False)  # api, database, ai, storage
    
    # Values
    value = Column(Float, nullable=False)
    unit = Column(String(50))  # ms, bytes, count, percent
    
    # Context
    endpoint = Column(String(255))
    method = Column(String(10))
    status_code = Column(Integer)
    
    # Additional data
    tags = Column(JSON, default={})
    
    # Timestamps
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_system_metrics_name", "metric_name"),
        Index("idx_system_metrics_category", "metric_category"),
        Index("idx_system_metrics_recorded_at", "recorded_at"),
    )
    
    def __repr__(self):
        return f"<SystemMetric(id={self.id}, name={self.metric_name})>"

