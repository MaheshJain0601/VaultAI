"""API router configuration."""
from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.metrics import router as metrics_router
from app.api.health import router as health_router

api_router = APIRouter()

api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(chat_router, prefix="/chat", tags=["Chat"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(health_router, prefix="/health", tags=["Health"])

