"""Health check and system status endpoints."""
import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.database import get_async_session
from app.config import settings
from app.schemas.metrics import SystemHealthResponse

router = APIRouter()

# Track app start time for uptime calculation
APP_START_TIME = time.time()


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "database_type": "supabase" if settings.is_using_supabase_db else "local",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_async_session)
):
    """
    Readiness check - verifies all dependencies are accessible.
    
    Checks:
    - Database connectivity (Supabase or local PostgreSQL)
    - Redis connectivity
    - Storage accessibility
    - Supabase features (if configured)
    """
    checks = {}
    overall_status = "healthy"
    
    # Check database (Supabase PostgreSQL or local)
    try:
        start = time.time()
        await db.execute(text("SELECT 1"))
        latency = int((time.time() - start) * 1000)
        checks["database"] = {
            "status": "healthy", 
            "latency_ms": latency,
            "type": "supabase" if settings.is_using_supabase_db else "local"
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"
    
    # Check Redis
    try:
        start = time.time()
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        latency = int((time.time() - start) * 1000)
        checks["redis"] = {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        checks["redis"] = {"status": "degraded", "error": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"
    
    # Check local storage
    try:
        from app.services.storage import storage_service
        await storage_service.initialize()
        checks["storage"] = {
            "status": "healthy",
            "type": "local",
            "path": str(storage_service.storage_path)
        }
    except Exception as e:
        checks["storage"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"
    
    # Check Supabase features (if configured)
    if settings.is_supabase_configured:
        try:
            from app.services.supabase_client import check_supabase_connection
            supabase_status = await check_supabase_connection()
            checks["supabase"] = supabase_status
        except Exception as e:
            checks["supabase"] = {"status": "error", "error": str(e)}
    else:
        checks["supabase"] = {"status": "not_configured"}
    
    # Check Google Gemini API (lightweight check)
    try:
        if settings.google_api_key:
            checks["gemini_api"] = {"status": "configured"}
        else:
            checks["gemini_api"] = {"status": "not_configured"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["gemini_api"] = {"status": "error", "error": str(e)}
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/detailed", response_model=SystemHealthResponse)
async def detailed_health(
    db: AsyncSession = Depends(get_async_session)
):
    """
    Detailed system health status with performance metrics.
    
    Returns comprehensive health information including:
    - Component health status
    - Active and pending task counts
    - Performance metrics
    """
    # Get basic checks first
    readiness = await readiness_check(db)
    
    # Calculate uptime
    uptime_seconds = time.time() - APP_START_TIME
    
    # Get task queue status from Redis
    active_tasks = 0
    pending_tasks = 0
    try:
        r = redis.from_url(settings.redis_url)
        pending_tasks = await r.llen("celery")  # Default Celery queue
        await r.close()
    except:
        pass
    
    # Get average latencies from recent system metrics
    from sqlalchemy import select, func
    from app.models.metrics import SystemMetric
    
    avg_api_result = await db.execute(
        select(func.avg(SystemMetric.value))
        .where(SystemMetric.metric_name == "api_latency")
    )
    avg_api_latency = float(avg_api_result.scalar() or 0)
    
    avg_processing_result = await db.execute(
        select(func.avg(SystemMetric.value))
        .where(SystemMetric.metric_name == "processing_time")
    )
    avg_processing_time = float(avg_processing_result.scalar() or 0)
    
    return SystemHealthResponse(
        status=readiness["status"],
        version=settings.app_version,
        uptime_seconds=uptime_seconds,
        database=readiness["checks"].get("database", {"status": "unknown"}),
        redis=readiness["checks"].get("redis", {"status": "unknown"}),
        storage=readiness["checks"].get("storage", {"status": "unknown"}),
        gemini_api=readiness["checks"].get("gemini_api", {"status": "unknown"}),
        active_tasks=active_tasks,
        pending_tasks=pending_tasks,
        avg_api_latency_ms=avg_api_latency,
        avg_processing_time_ms=avg_processing_time,
        checked_at=datetime.utcnow()
    )


@router.get("/live")
async def liveness_check():
    """
    Liveness check - simple check that the service is running.
    
    Used by container orchestrators to determine if the service
    should be restarted.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/supabase")
async def supabase_status():
    """
    Check Supabase database connection status.
    
    Returns information about Supabase database configuration and connectivity.
    Note: Storage is always local, not Supabase.
    """
    from app.services.supabase_client import check_supabase_connection
    
    status = await check_supabase_connection()
    status["using_supabase_db"] = settings.is_using_supabase_db
    status["storage"] = "local"
    
    return status
