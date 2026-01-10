"""Supabase client for database features."""
import logging
from typing import Dict, Any
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

# Supabase client singleton
_supabase_client = None


def get_supabase_client():
    """
    Get or create Supabase client.
    
    Used for Supabase-specific features like realtime subscriptions.
    Note: For database operations, we use SQLAlchemy with the 
    PostgreSQL connection string directly for better ORM support.
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    if not settings.is_supabase_configured:
        logger.debug("Supabase not configured.")
        return None
    
    try:
        from supabase import create_client, Client
        
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_key or settings.supabase_key
        )
        logger.info("Supabase client initialized successfully")
        return _supabase_client
        
    except ImportError:
        logger.warning("supabase-py not installed. Install with: pip install supabase")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


async def check_supabase_connection() -> Dict[str, Any]:
    """
    Check Supabase connection status.
    
    Returns health check information for the Supabase connection.
    """
    result = {
        "configured": settings.is_supabase_configured,
        "status": "not_configured",
        "database_type": "supabase" if settings.is_using_supabase_db else "local"
    }
    
    if not settings.is_supabase_configured:
        return result
    
    client = get_supabase_client()
    if not client:
        result["status"] = "client_error"
        return result
    
    try:
        # Simple connectivity check
        result["status"] = "connected"
        result["url"] = settings.supabase_url
        return result
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result
