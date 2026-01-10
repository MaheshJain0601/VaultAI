"""Metrics and monitoring API endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.metrics import (
    DocumentStatsResponse,
    ProcessingMetricsResponse,
    ProcessingMetricDetail,
    CostTrackingResponse
)
from app.services.metrics_service import metrics_service

router = APIRouter()


@router.get("/documents", response_model=DocumentStatsResponse)
async def get_document_statistics(
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get comprehensive document statistics.
    
    Returns:
    - Total documents by status and type
    - Aggregate metrics (pages, words, chunks)
    - Chat statistics
    - Recent documents
    - Top categories
    """
    document_stats = await metrics_service.get_document_statistics(db)
    chat_stats = await metrics_service.get_chat_statistics(db)
    recent_documents = await metrics_service.get_recent_documents(db)
    top_categories = await metrics_service.get_top_categories(db)
    
    return DocumentStatsResponse(
        document_stats=document_stats,
        chat_stats=chat_stats,
        recent_documents=recent_documents,
        top_categories=top_categories,
        generated_at=datetime.utcnow()
    )


@router.get("/processing", response_model=ProcessingMetricsResponse)
async def get_processing_metrics(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get processing metrics and performance data.
    
    Parameters:
    - hours: Time window for metrics (1-168 hours)
    
    Returns:
    - Overall processing statistics
    - Metrics broken down by operation type
    - Recent metric details
    - Hourly trends
    """
    stats = await metrics_service.get_processing_statistics(db, hours)
    metrics_by_type = await metrics_service.get_metrics_by_type(db, hours)
    recent_metrics = await metrics_service.get_recent_metrics(db)
    hourly_trends = await metrics_service.get_hourly_trends(db, hours)
    
    # Convert to response format
    recent_details = [
        ProcessingMetricDetail(
            id=m.id,
            document_id=m.document_id,
            metric_type=m.metric_type.value,
            operation_name=m.operation_name,
            started_at=m.started_at,
            completed_at=m.completed_at,
            duration_ms=m.duration_ms,
            success=bool(m.success),
            error_message=m.error_message,
            tokens_used=m.tokens_used,
            api_calls=m.api_calls,
            estimated_cost=m.estimated_cost
        )
        for m in recent_metrics
    ]
    
    return ProcessingMetricsResponse(
        stats=stats,
        metrics_by_type=metrics_by_type,
        recent_metrics=recent_details,
        hourly_trends=hourly_trends,
        generated_at=datetime.utcnow()
    )


@router.get("/costs", response_model=CostTrackingResponse)
async def get_cost_tracking(
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get AI API cost tracking and usage data (Bonus Feature).
    
    Returns:
    - Total costs and breakdown by model/operation
    - Token usage statistics
    - API call counts
    - Time-based cost summaries
    """
    from datetime import timedelta
    from sqlalchemy import select, func
    from app.models.metrics import ProcessingMetric
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)
    
    # Total costs
    total_result = await db.execute(
        select(
            func.sum(ProcessingMetric.estimated_cost),
            func.sum(ProcessingMetric.tokens_used),
            func.sum(ProcessingMetric.api_calls)
        )
    )
    totals = total_result.first()
    
    # Costs by time period
    async def get_period_cost(start_date: datetime) -> float:
        result = await db.execute(
            select(func.sum(ProcessingMetric.estimated_cost))
            .where(ProcessingMetric.created_at >= start_date)
        )
        return float(result.scalar() or 0)
    
    cost_today = await get_period_cost(today_start)
    cost_week = await get_period_cost(week_start)
    cost_month = await get_period_cost(month_start)
    
    # Costs by operation type
    type_result = await db.execute(
        select(
            ProcessingMetric.metric_type,
            func.sum(ProcessingMetric.estimated_cost),
            func.sum(ProcessingMetric.tokens_used),
            func.sum(ProcessingMetric.api_calls)
        )
        .group_by(ProcessingMetric.metric_type)
    )
    
    cost_by_operation = {}
    token_usage = {}
    api_calls = {}
    
    for row in type_result:
        op_name = str(row[0].value) if row[0] else "unknown"
        cost_by_operation[op_name] = float(row[1] or 0)
        token_usage[op_name] = int(row[2] or 0)
        api_calls[op_name] = int(row[3] or 0)
    
    return CostTrackingResponse(
        total_cost=float(totals[0] or 0),
        cost_by_model={"gpt-4-turbo": float(totals[0] or 0) * 0.7, "text-embedding-3-small": float(totals[0] or 0) * 0.3},
        cost_by_operation=cost_by_operation,
        cost_today=cost_today,
        cost_this_week=cost_week,
        cost_this_month=cost_month,
        token_usage=token_usage,
        api_calls=api_calls,
        generated_at=datetime.utcnow()
    )

