"""Database configuration and session management."""
import asyncio
import logging
import socket
import ssl
from urllib.parse import urlparse, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

# Connection pool settings optimized for Supabase
# Supabase free tier has limited connections, so we use conservative settings
POOL_SIZE = 5 if settings.is_using_supabase_db else 10
MAX_OVERFLOW = 10 if settings.is_using_supabase_db else 20


def _resolve_hostname_to_ipv4(url: str) -> str:
    """
    Resolve hostname in database URL to IPv4 address.
    This helps avoid IPv6 routing issues in Docker on macOS.
    """
    try:
        parsed = urlparse(url)
        if parsed.hostname:
            # Get IPv4 address only (AF_INET) 
            ip = socket.gethostbyname(parsed.hostname)
            logger.info(f"Resolved {parsed.hostname} to {ip}")
            # Replace hostname with IP in URL
            netloc = parsed.netloc.replace(parsed.hostname, ip)
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception as e:
        logger.warning(f"Could not resolve hostname to IPv4: {e}")
    return url


# Resolve hostnames to IPv4 for Supabase to avoid Docker IPv6 issues
database_url = settings.database_url
sync_database_url = settings.sync_database_url
if settings.is_using_supabase_db:
    database_url = _resolve_hostname_to_ipv4(settings.database_url)
    sync_database_url = _resolve_hostname_to_ipv4(settings.sync_database_url)

# Parse database URL for asyncpg connection
parsed_url = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://"))

# Create SSL context for Supabase
ssl_context = None
if settings.is_using_supabase_db:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    logger.info("Using Supabase database configuration with SSL")


async def _create_asyncpg_connection():
    """Custom connection creator with statement_cache_size=0 for pgbouncer compatibility."""
    return await asyncpg.connect(
        host=parsed_url.hostname,
        port=parsed_url.port or 5432,
        user=parsed_url.username,
        password=parsed_url.password,
        database=parsed_url.path.lstrip('/'),
        ssl=ssl_context if settings.is_using_supabase_db else None,
        statement_cache_size=0,  # Critical for pgbouncer/Supabase pooler
        server_settings={"application_name": "vault-ai"},
    )


# Create async engine with appropriate pool configuration
# IMPORTANT: Disable asyncpg's prepared statement cache for pgbouncer compatibility
async_engine = create_async_engine(
    database_url,
    echo=settings.debug,
    poolclass=NullPool,  # Always use NullPool for pgbouncer compatibility
    connect_args={
        # Disable asyncpg's native prepared statement cache (critical for pgbouncer/Supabase)
        "statement_cache_size": 0,
        # Disable asyncpg's prepared statement name generation
        "prepared_statement_name_func": lambda: "",
        "server_settings": {"application_name": "vault-ai"},
        **({"ssl": ssl_context} if ssl_context else {}),
    },
)

# Sync engine for Celery workers
sync_engine = create_engine(
    sync_database_url,
    echo=settings.debug,
    pool_size=POOL_SIZE // 2,
    max_overflow=MAX_OVERFLOW // 2,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Session factories
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)

# Base class for models
Base = declarative_base()


async def get_async_session() -> AsyncSession:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    """Get sync database session for Celery workers."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def reset_db():
    """
    Reset (drop and recreate) all database tables.
    
    WARNING: This will delete ALL data in the database!
    Only use this in development or when RESET_DB_ON_STARTUP is enabled.
    """
    logger.warning("=" * 60)
    logger.warning("RESETTING DATABASE - ALL DATA WILL BE DELETED!")
    logger.warning("=" * 60)
    
    async with async_engine.begin() as conn:
        # Drop all tables
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("All tables dropped")
        
        # Drop enum types that SQLAlchemy creates
        try:
            await conn.execute(text("DROP TYPE IF EXISTS documenttype CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS documentstatus CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS messagerole CASCADE"))
            await conn.execute(text("DROP TYPE IF EXISTS metrictype CASCADE"))
            logger.info("Enum types dropped")
        except Exception as e:
            logger.warning(f"Could not drop enum types (may not exist): {e}")
    
    logger.info("Database reset complete")


async def init_db():
    """
    Initialize database tables.
    
    For Supabase, tables can also be created via the Supabase Dashboard
    or SQL editor. This function creates them programmatically.
    
    If RESET_DB_ON_STARTUP is enabled, all tables will be dropped first.
    """
    # Check if reset is enabled
    if settings.reset_db_on_startup:
        logger.warning("RESET_DB_ON_STARTUP is enabled - resetting database...")
        await reset_db()
    
    logger.info("Initializing database tables...")
    
    async with async_engine.begin() as conn:
        # Enable pgvector extension if using Supabase or local with pgvector
        if settings.enable_pgvector:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector extension enabled")
            except Exception as e:
                logger.warning(f"Could not enable pgvector extension: {e}")
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables initialized successfully")


async def close_db():
    """Close database connections."""
    await async_engine.dispose()
    logger.info("Database connections closed")


async def check_db_connection() -> dict:
    """
    Check database connection health.
    
    Returns status information for health checks.
    """
    import time
    
    result = {
        "status": "unknown",
        "is_supabase": settings.is_using_supabase_db,
        "latency_ms": None
    }
    
    try:
        start = time.time()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        
        latency = int((time.time() - start) * 1000)
        result["status"] = "healthy"
        result["latency_ms"] = latency
        
    except Exception as e:
        result["status"] = "unhealthy"
        result["error"] = str(e)
    
    return result


# SQL for creating tables with pgvector (can be run in Supabase SQL Editor)
SUPABASE_INIT_SQL = """
-- Enable pgvector extension (usually already enabled in Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INTEGER NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    title VARCHAR(500),
    description TEXT,
    page_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processing_error TEXT,
    processing_duration_ms INTEGER,
    summary TEXT,
    key_topics TEXT[],
    categories TEXT[],
    sentiment VARCHAR(50),
    language VARCHAR(50) DEFAULT 'en',
    embedding_model VARCHAR(100),
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    embedding vector(768),  -- Google text-embedding-004 dimension
    embedding_model VARCHAR(100),
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    title VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    document_ids UUID[],
    context_window INTEGER DEFAULT 5,
    message_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP
);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    context_chunks JSONB DEFAULT '[]',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    model_used VARCHAR(100),
    response_time_ms INTEGER,
    confidence_score FLOAT,
    suggested_questions TEXT[],
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_sessions_document_id ON chat_sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON chat_messages(session_id);
"""
