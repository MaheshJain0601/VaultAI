"""Metrics service for tracking and reporting system metrics."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.chat import ChatSession, ChatMessage, MessageRole
from app.models.metrics import ProcessingMetric, SystemMetric, MetricType


class MetricsService:
    """Service for tracking and retrieving system metrics."""
    
    async def record_processing_metric(
        self,
        db: AsyncSession,
        metric_type: MetricType,
        operation_name: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        document_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        tokens_used: int = 0,
        api_calls: int = 0,
        metadata: Optional[Dict] = None
    ) -> ProcessingMetric:
        """Record a processing metric."""
        duration_ms = None
        if completed_at:
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        
        # Estimate cost based on tokens
        estimated_cost = self._estimate_cost(tokens_used, metric_type)
        
        metric = ProcessingMetric(
            document_id=document_id,
            session_id=session_id,
            metric_type=metric_type,
            operation_name=operation_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            success=1 if success else 0,
            error_message=error_message,
            tokens_used=tokens_used,
            api_calls=api_calls,
            estimated_cost=estimated_cost,
            metadata=metadata or {}
        )
        
        db.add(metric)
        await db.commit()
        return metric
    
    async def record_system_metric(
        self,
        db: AsyncSession,
        metric_name: str,
        metric_category: str,
        value: float,
        unit: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        tags: Optional[Dict] = None
    ) -> SystemMetric:
        """Record a system-level metric."""
        metric = SystemMetric(
            metric_name=metric_name,
            metric_category=metric_category,
            value=value,
            unit=unit,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            tags=tags or {}
        )
        
        db.add(metric)
        await db.commit()
        return metric
    
    async def get_document_statistics(self, db: AsyncSession) -> Dict:
        """Get comprehensive document statistics."""
        # Total documents by status
        status_result = await db.execute(
            select(Document.status, func.count(Document.id))
            .group_by(Document.status)
        )
        documents_by_status = {str(row[0].value): row[1] for row in status_result}
        
        # Total documents by type
        type_result = await db.execute(
            select(Document.file_type, func.count(Document.id))
            .group_by(Document.file_type)
        )
        documents_by_type = {str(row[0].value): row[1] for row in type_result}
        
        # Aggregate stats
        agg_result = await db.execute(
            select(
                func.count(Document.id),
                func.sum(Document.page_count),
                func.sum(Document.word_count),
                func.avg(Document.file_size),
                func.avg(Document.processing_duration_ms)
            )
        )
        row = agg_result.first()
        
        # Total chunks
        chunk_result = await db.execute(select(func.count(DocumentChunk.id)))
        total_chunks = chunk_result.scalar() or 0
        
        return {
            "total_documents": row[0] or 0,
            "documents_by_status": documents_by_status,
            "documents_by_type": documents_by_type,
            "total_pages": row[1] or 0,
            "total_words": row[2] or 0,
            "total_chunks": total_chunks,
            "average_document_size_bytes": float(row[3] or 0),
            "average_processing_time_ms": float(row[4] or 0)
        }
    
    async def get_chat_statistics(self, db: AsyncSession) -> Dict:
        """Get chat session statistics."""
        # Session counts
        session_result = await db.execute(
            select(
                func.count(ChatSession.id),
                func.count(case((ChatSession.is_active == True, 1)))
            )
        )
        session_row = session_result.first()
        
        # Message counts
        message_result = await db.execute(
            select(
                func.count(ChatMessage.id),
                func.count(case((ChatMessage.role == MessageRole.USER, 1))),
                func.count(case((ChatMessage.role == MessageRole.ASSISTANT, 1))),
                func.sum(ChatMessage.total_tokens),
                func.avg(ChatMessage.response_time_ms)
            )
        )
        msg_row = message_result.first()
        
        total_sessions = session_row[0] or 0
        total_messages = msg_row[0] or 0
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": session_row[1] or 0,
            "total_messages": total_messages,
            "user_messages": msg_row[1] or 0,
            "assistant_messages": msg_row[2] or 0,
            "average_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0,
            "total_tokens_used": msg_row[3] or 0,
            "average_response_time_ms": float(msg_row[4] or 0)
        }
    
    async def get_processing_statistics(
        self,
        db: AsyncSession,
        hours: int = 24
    ) -> Dict:
        """Get processing metrics statistics."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Overall stats
        result = await db.execute(
            select(
                func.count(ProcessingMetric.id),
                func.sum(case((ProcessingMetric.success == 1, 1), else_=0)),
                func.sum(case((ProcessingMetric.success == 0, 1), else_=0)),
                func.avg(ProcessingMetric.duration_ms),
                func.sum(ProcessingMetric.tokens_used),
                func.sum(ProcessingMetric.api_calls),
                func.sum(ProcessingMetric.estimated_cost)
            ).where(ProcessingMetric.created_at >= cutoff)
        )
        row = result.first()
        
        total = row[0] or 0
        success = row[1] or 0
        
        return {
            "total_operations": total,
            "successful_operations": success,
            "failed_operations": row[2] or 0,
            "success_rate": success / total if total > 0 else 1.0,
            "average_duration_ms": float(row[3] or 0),
            "total_tokens_used": row[4] or 0,
            "total_api_calls": row[5] or 0,
            "estimated_total_cost": float(row[6] or 0)
        }
    
    async def get_metrics_by_type(
        self,
        db: AsyncSession,
        hours: int = 24
    ) -> Dict[str, Dict]:
        """Get processing metrics grouped by type."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        result = await db.execute(
            select(
                ProcessingMetric.metric_type,
                func.count(ProcessingMetric.id),
                func.sum(case((ProcessingMetric.success == 1, 1), else_=0)),
                func.avg(ProcessingMetric.duration_ms),
                func.sum(ProcessingMetric.tokens_used),
                func.sum(ProcessingMetric.api_calls),
                func.sum(ProcessingMetric.estimated_cost)
            )
            .where(ProcessingMetric.created_at >= cutoff)
            .group_by(ProcessingMetric.metric_type)
        )
        
        metrics_by_type = {}
        for row in result:
            metric_type = str(row[0].value) if row[0] else "unknown"
            total = row[1] or 0
            success = row[2] or 0
            metrics_by_type[metric_type] = {
                "total_operations": total,
                "successful_operations": success,
                "failed_operations": total - success,
                "success_rate": success / total if total > 0 else 1.0,
                "average_duration_ms": float(row[3] or 0),
                "total_tokens_used": row[4] or 0,
                "total_api_calls": row[5] or 0,
                "estimated_total_cost": float(row[6] or 0)
            }
        
        return metrics_by_type
    
    async def get_recent_documents(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """Get recently uploaded documents."""
        result = await db.execute(
            select(Document)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        documents = result.scalars().all()
        
        return [
            {
                "id": str(doc.id),
                "filename": doc.original_filename,
                "file_type": str(doc.file_type.value),
                "status": str(doc.status.value),
                "created_at": doc.created_at.isoformat()
            }
            for doc in documents
        ]
    
    async def get_top_categories(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """Get most common document categories."""
        # This requires unnesting the categories array
        result = await db.execute(
            select(
                func.unnest(Document.categories).label("category"),
                func.count().label("count")
            )
            .group_by("category")
            .order_by(func.count().desc())
            .limit(limit)
        )
        
        return [
            {"category": row[0], "count": row[1]}
            for row in result
        ]
    
    async def get_hourly_trends(
        self,
        db: AsyncSession,
        hours: int = 24
    ) -> List[Dict]:
        """Get processing metrics trends by hour."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        result = await db.execute(
            select(
                func.date_trunc('hour', ProcessingMetric.created_at).label("hour"),
                func.count(ProcessingMetric.id),
                func.sum(case((ProcessingMetric.success == 1, 1), else_=0)),
                func.avg(ProcessingMetric.duration_ms),
                func.sum(ProcessingMetric.tokens_used)
            )
            .where(ProcessingMetric.created_at >= cutoff)
            .group_by("hour")
            .order_by("hour")
        )
        
        return [
            {
                "hour": row[0].isoformat() if row[0] else None,
                "operations": row[1] or 0,
                "successful": row[2] or 0,
                "avg_duration_ms": float(row[3] or 0),
                "tokens_used": row[4] or 0
            }
            for row in result
        ]
    
    async def get_recent_metrics(
        self,
        db: AsyncSession,
        limit: int = 50
    ) -> List[ProcessingMetric]:
        """Get recent processing metrics."""
        result = await db.execute(
            select(ProcessingMetric)
            .order_by(ProcessingMetric.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    def _estimate_cost(self, tokens: int, metric_type: MetricType) -> float:
        """Estimate cost based on token usage and operation type."""
        # Pricing estimates (per 1K tokens)
        pricing = {
            MetricType.EMBEDDING: 0.0001,  # text-embedding-3-small
            MetricType.AI_ANALYSIS: 0.01,  # GPT-4 Turbo input
            MetricType.CHAT_QUERY: 0.01,  # GPT-4 Turbo input
        }
        
        rate = pricing.get(metric_type, 0.01)
        return (tokens / 1000) * rate


# Singleton instance
metrics_service = MetricsService()

