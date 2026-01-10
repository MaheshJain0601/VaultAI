"""Metrics-related Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentStats(BaseModel):
    """Statistics about documents in the system."""
    total_documents: int
    documents_by_status: Dict[str, int]
    documents_by_type: Dict[str, int]
    total_pages: int
    total_words: int
    total_chunks: int
    average_document_size_bytes: float
    average_processing_time_ms: float


class ProcessingStats(BaseModel):
    """Statistics about processing operations."""
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    average_duration_ms: float
    total_tokens_used: int
    total_api_calls: int
    estimated_total_cost: float


class ChatStats(BaseModel):
    """Statistics about chat sessions."""
    total_sessions: int
    active_sessions: int
    total_messages: int
    user_messages: int
    assistant_messages: int
    average_messages_per_session: float
    total_tokens_used: int
    average_response_time_ms: float


class DocumentStatsResponse(BaseModel):
    """Response schema for document statistics endpoint."""
    document_stats: DocumentStats
    chat_stats: ChatStats
    recent_documents: List[Dict]  # List of recent document summaries
    top_categories: List[Dict]  # Most common categories
    generated_at: datetime


class ProcessingMetricDetail(BaseModel):
    """Detail of a single processing metric."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    document_id: Optional[UUID] = None
    metric_type: str
    operation_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    tokens_used: int
    api_calls: int
    estimated_cost: float


class ProcessingMetricsResponse(BaseModel):
    """Response schema for processing metrics endpoint."""
    stats: ProcessingStats
    metrics_by_type: Dict[str, ProcessingStats]
    recent_metrics: List[ProcessingMetricDetail]
    hourly_trends: List[Dict]  # Metrics grouped by hour
    generated_at: datetime


class SystemHealthResponse(BaseModel):
    """Response schema for system health endpoint."""
    status: str  # healthy, degraded, unhealthy
    version: str
    uptime_seconds: float
    
    # Component health
    database: Dict[str, Any]  # status, latency_ms, type
    redis: Dict[str, Any]  # status, latency_ms
    storage: Dict[str, Any]  # status, type, path
    gemini_api: Dict[str, Any]  # status
    
    # Resource usage
    active_tasks: int
    pending_tasks: int
    
    # Performance
    avg_api_latency_ms: float
    avg_processing_time_ms: float
    
    checked_at: datetime


class CostTrackingResponse(BaseModel):
    """Response schema for AI cost tracking (bonus feature)."""
    total_cost: float
    cost_by_model: Dict[str, float]
    cost_by_operation: Dict[str, float]
    cost_today: float
    cost_this_week: float
    cost_this_month: float
    token_usage: Dict[str, int]
    api_calls: Dict[str, int]
    generated_at: datetime

