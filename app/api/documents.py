"""Document management API endpoints."""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.document import Document, DocumentChunk, DocumentInsight, DocumentStatus, DocumentType
from app.schemas.document import (
    DocumentResponse, 
    DocumentListResponse, 
    DocumentUploadResponse,
    DocumentInsightResponse,
    DocumentStatusResponse,
    DocumentSummaryRequest,
    DocumentAnalysisResponse
)
from app.services.storage import storage_service
from app.workers.tasks import process_document_task

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Upload a new document for processing.
    
    The document will be validated, stored, and queued for async processing
    which includes:
    - Text extraction
    - Chunking for RAG
    - Embedding generation
    - AI-powered analysis (summary, topics, categories)
    """
    # Validate file type
    if not storage_service.validate_file_type(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(storage_service.allowed_extensions_list)}"
        )
    
    # Read file content
    file_content = await file.read()
    
    # Validate file size
    if not storage_service.validate_file_size(len(file_content)):
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {storage_service.max_file_size_mb}MB"
        )
    
    # Save file to storage
    generated_filename, file_path, file_size = await storage_service.save_file(
        file_content, file.filename
    )
    
    # Get file type
    file_type = storage_service.get_file_type(file.filename)
    
    # Create document record
    document = Document(
        filename=generated_filename,
        original_filename=file.filename,
        file_type=DocumentType(file_type),
        file_size=file_size,
        file_path=file_path,
        title=title,
        description=description,
        status=DocumentStatus.PENDING
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Queue for async processing
    process_document_task.delay(str(document.id))
    
    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        file_type=file_type,
        file_size=file_size,
        status=document.status.value,
        created_at=document.created_at
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    file_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """
    List all documents with pagination and filtering.
    
    Filters:
    - status: Filter by processing status
    - file_type: Filter by document type (pdf, docx, txt, md)
    - search: Search in filename, title, or summary
    """
    query = select(Document)
    count_query = select(func.count(Document.id))
    
    # Apply filters
    if status:
        try:
            status_enum = DocumentStatus(status)
            query = query.where(Document.status == status_enum)
            count_query = count_query.where(Document.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    if file_type:
        try:
            type_enum = DocumentType(file_type)
            query = query.where(Document.file_type == type_enum)
            count_query = count_query.where(Document.file_type == type_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Document.original_filename.ilike(search_pattern)) |
            (Document.title.ilike(search_pattern)) |
            (Document.summary.ilike(search_pattern))
        )
        count_query = count_query.where(
            (Document.original_filename.ilike(search_pattern)) |
            (Document.title.ilike(search_pattern)) |
            (Document.summary.ilike(search_pattern))
        )
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Get document details by ID."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Get document processing status."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentStatusResponse(
        id=document.id,
        status=document.status.value,
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        processing_error=document.processing_error,
        processing_duration_ms=document.processing_duration_ms
    )


@router.get("/{document_id}/insights", response_model=List[DocumentInsightResponse])
async def get_document_insights(
    document_id: uuid.UUID,
    insight_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get AI-generated insights for a document.
    
    Insight types include:
    - summary: Document summary
    - key_points: Main points and findings
    - entities: Named entities (people, orgs, locations)
    - action_items: Recommended actions
    """
    # Verify document exists
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    if not doc_result.scalar():
        raise HTTPException(status_code=404, detail="Document not found")
    
    query = select(DocumentInsight).where(DocumentInsight.document_id == document_id)
    
    if insight_type:
        query = query.where(DocumentInsight.insight_type == insight_type)
    
    result = await db.execute(query.order_by(DocumentInsight.created_at))
    insights = result.scalars().all()
    
    return [DocumentInsightResponse.model_validate(insight) for insight in insights]


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Delete a document and all associated data."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from storage
    await storage_service.delete_file(document.filename)
    
    # Delete from database (cascades to chunks, insights, sessions)
    await db.delete(document)
    await db.commit()
    
    return {"message": "Document deleted successfully", "id": str(document_id)}


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Re-queue a document for processing (useful after failures)."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Reset status
    document.status = DocumentStatus.PENDING
    document.processing_error = None
    document.processing_started_at = None
    document.processing_completed_at = None
    
    await db.commit()
    
    # Queue for processing
    process_document_task.delay(str(document_id))
    
    return {
        "message": "Document queued for reprocessing",
        "id": str(document_id),
        "status": "pending"
    }


@router.post("/{document_id}/summarize")
async def generate_custom_summary(
    document_id: uuid.UUID,
    request: DocumentSummaryRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Generate a customized summary for a document.
    
    Allows customization of:
    - length: short, medium, or long
    - focus_areas: Specific topics to emphasize
    - tone: professional, casual, or technical
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail="Document processing not complete"
        )
    
    # Get document chunks to reconstruct text
    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()
    
    if not chunks:
        raise HTTPException(status_code=400, detail="No content available")
    
    # Reconstruct text (limited for API usage)
    text = "\n\n".join([chunk.content for chunk in chunks[:20]])
    
    from app.services.ai_service import ai_service
    
    summary, metadata = await ai_service.generate_summary(
        text,
        length=request.length,
        focus_areas=request.focus_areas,
        tone=request.tone
    )
    
    return {
        "document_id": str(document_id),
        "summary": summary,
        "length": request.length,
        "focus_areas": request.focus_areas,
        "tone": request.tone,
        "tokens_used": metadata.get("total_tokens", 0)
    }


@router.get("/{document_id}/analysis", response_model=DocumentAnalysisResponse)
async def get_document_analysis(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Get comprehensive AI-powered analysis of a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Document processing not complete"
        )
    
    # Get all insights
    insights_result = await db.execute(
        select(DocumentInsight).where(DocumentInsight.document_id == document_id)
    )
    insights = insights_result.scalars().all()
    
    # Parse key_points from insights
    key_points = []
    entities = []
    for insight in insights:
        if insight.insight_type == "key_points":
            try:
                import json
                data = json.loads(insight.content) if isinstance(insight.content, str) else insight.content
                key_points = data.get("key_points", [])
                entities = data.get("entities", [])
            except:
                pass
    
    # Calculate reading time (average 200 words per minute)
    reading_time = max(1, document.word_count // 200) if document.word_count else 1
    
    # Simple complexity score based on word/sentence ratio
    complexity_score = min(10, max(1, (document.word_count or 100) / (document.page_count or 1) / 50))
    
    return DocumentAnalysisResponse(
        document_id=document.id,
        summary=document.summary or "",
        key_topics=document.key_topics or [],
        key_points=key_points,
        entities=entities,
        categories=document.categories or [],
        sentiment=document.sentiment or "neutral",
        sentiment_score=0.0,
        language=document.language or "en",
        reading_time_minutes=reading_time,
        complexity_score=complexity_score,
        insights=[DocumentInsightResponse.model_validate(i) for i in insights]
    )

