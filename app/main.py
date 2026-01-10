"""Main FastAPI application entry point."""
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
from app.api import api_router

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize database tables
    await init_db()
    logger.info("Database initialized")
    
    # Initialize storage
    from app.services.storage import storage_service
    await storage_service.initialize()
    logger.info("Storage initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
# Vault AI - AI-Powered Document Management System

An intelligent document management system that enables:

- **Document Upload & Processing**: Upload PDF, DOCX, TXT, and Markdown files for automated processing
- **AI-Powered Analysis**: Automatic summarization, topic extraction, categorization, and sentiment analysis
- **Document Chat (RAG)**: Ask questions about your documents and get accurate, cited answers
- **Multi-turn Conversations**: Maintain context across multiple questions
- **Metrics & Monitoring**: Track processing metrics, costs, and system health

## Key Features

### Document Management
- Upload documents with automatic text extraction
- Async processing pipeline with status tracking
- Search and filter documents
- Custom summary generation

### RAG-Powered Chat
- Semantic search over document content
- Multi-turn conversation support
- Source citations for transparency
- Follow-up question suggestions

### Analytics & Monitoring
- Processing metrics and trends
- Cost tracking for AI API usage
- System health monitoring

## Getting Started

1. Upload a document via `POST /api/v1/documents/upload`
2. Wait for processing to complete (check status via `GET /api/v1/documents/{id}/status`)
3. Start a chat session via `POST /api/v1/chat/sessions`
4. Ask questions via `POST /api/v1/chat/sessions/{id}/ask`
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next: Callable) -> Response:
    """Add request timing to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Serve frontend static files (CSS, JS)
# Mount these AFTER API routes but BEFORE the catch-all root endpoint
@app.get("/styles.css")
async def serve_css():
    """Serve the CSS file."""
    css_path = FRONTEND_DIR / "styles.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    return Response(status_code=404)


@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_path = FRONTEND_DIR / "app.js"
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    return Response(status_code=404)


# Root endpoint - serve frontend
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend application."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    # Fallback to API info if frontend not found
    return HTMLResponse(content=f"""
        <html>
            <head><title>{settings.app_name}</title></head>
            <body>
                <h1>{settings.app_name} v{settings.app_version}</h1>
                <p>Frontend not found. API is available at:</p>
                <ul>
                    <li><a href="/docs">API Documentation</a></li>
                    <li><a href="/api/v1/health/">Health Check</a></li>
                </ul>
            </body>
        </html>
    """)


# API info endpoint (moved from root)
@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-Powered Document Management System",
        "docs": "/docs",
        "health": "/api/v1/health/",
        "api": "/api/v1/"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )

