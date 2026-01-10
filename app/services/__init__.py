"""Service layer for Vault AI."""
from app.services.storage import StorageService, storage_service
from app.services.document_processor import DocumentProcessor, document_processor
from app.services.ai_service import AIService, ai_service
from app.services.rag_service import RAGService, rag_service
from app.services.metrics_service import MetricsService, metrics_service
from app.services.supabase_client import get_supabase_client, check_supabase_connection

__all__ = [
    # Classes
    "StorageService",
    "DocumentProcessor",
    "AIService",
    "RAGService",
    "MetricsService",
    # Singleton instances
    "storage_service",
    "document_processor",
    "ai_service",
    "rag_service",
    "metrics_service",
    # Supabase (database only)
    "get_supabase_client",
    "check_supabase_connection",
]

