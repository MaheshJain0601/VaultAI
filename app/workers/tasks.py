"""Celery tasks for async document processing with rate limiting."""
import json
import logging
from datetime import datetime
from uuid import UUID

from celery import shared_task

from app.workers.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models.document import Document, DocumentChunk, DocumentInsight, DocumentStatus
from app.models.metrics import ProcessingMetric, MetricType
from app.services.document_processor import document_processor
from app.services.ai_service import AIService
from app.services.rate_limiter import get_rate_limiter
from app.config import settings

logger = logging.getLogger(__name__)

# Get the rate limiter for synchronous use in Celery
rate_limiter = get_rate_limiter()


@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str):
    """
    Main document processing task.
    
    Orchestrates the full processing pipeline:
    1. Text extraction from document
    2. Text chunking for RAG
    3. Embedding generation for each chunk
    4. AI analysis (summary, topics, categories, sentiment)
    5. Insight extraction
    
    This task is idempotent - can be safely retried on failure.
    """
    logger.info(f"Starting processing for document {document_id}")
    
    session = SyncSessionLocal()
    ai_service = AIService()
    total_tokens = 0
    total_api_calls = 0
    
    try:
        # Get document
        document = session.query(Document).filter(Document.id == UUID(document_id)).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"status": "error", "message": "Document not found"}
        
        # Update status to processing
        document.status = DocumentStatus.PROCESSING
        document.processing_started_at = datetime.utcnow()
        session.commit()
        
        # Record processing start metric
        start_time = datetime.utcnow()
        
        # Step 1: Extract text
        logger.info(f"Extracting text from {document.original_filename}")
        extracted = document_processor.extract_text(
            document.file_path, 
            document.file_type.value
        )
        
        # Update document metadata
        document.page_count = extracted.page_count
        document.word_count = extracted.word_count
        document.character_count = extracted.character_count
        if extracted.metadata.get("title"):
            document.title = document.title or extracted.metadata["title"]
        session.commit()
        
        # Record extraction metric
        _record_metric(
            session, document.id, MetricType.TEXT_EXTRACTION,
            "extract_text", start_time, datetime.utcnow()
        )
        
        # Step 2: Chunk text
        logger.info("Chunking text for RAG")
        document.status = DocumentStatus.CHUNKING
        session.commit()
        
        chunk_start = datetime.utcnow()
        chunks = document_processor.chunk_text(extracted)
        
        # Clear existing chunks
        session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).delete()
        
        # Save chunks (without embeddings first)
        chunk_objects = []
        for chunk in chunks:
            chunk_obj = DocumentChunk(
                document_id=document.id,
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                token_count=chunk.token_count
            )
            session.add(chunk_obj)
            chunk_objects.append(chunk_obj)
        
        document.chunk_count = len(chunks)
        session.commit()
        
        _record_metric(
            session, document.id, MetricType.CHUNKING,
            "chunk_text", chunk_start, datetime.utcnow(),
            metadata={"chunk_count": len(chunks)}
        )
        
        # Step 3: Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        document.status = DocumentStatus.EMBEDDING
        session.commit()
        
        embedding_start = datetime.utcnow()
        
        # Get chunk texts for batch embedding
        chunk_texts = [chunk.content for chunk in chunks]
        
        # Generate embeddings in batch (sync wrapper for async)
        # Apply rate limiting before the API call
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Rate limit before embedding generation
            logger.info("Waiting for rate limit before generating embeddings...")
            rate_limiter.wait_sync()
            embeddings = loop.run_until_complete(
                ai_service.generate_embeddings_batch(chunk_texts)
            )
        finally:
            loop.close()
        
        # Update chunks with embeddings
        for chunk_obj, embedding in zip(chunk_objects, embeddings):
            chunk_obj.embedding = embedding
            chunk_obj.embedding_model = settings.embedding_model
        
        document.embedding_model = settings.embedding_model
        session.commit()
        
        total_api_calls += 1
        embedding_tokens = sum(len(t.split()) * 2 for t in chunk_texts)  # Rough estimate
        total_tokens += embedding_tokens
        
        _record_metric(
            session, document.id, MetricType.EMBEDDING,
            "generate_embeddings", embedding_start, datetime.utcnow(),
            tokens=embedding_tokens, api_calls=1
        )
        
        # Step 4: AI Analysis
        logger.info("Performing AI analysis with rate limiting")
        document.status = DocumentStatus.ANALYZING
        session.commit()
        
        analysis_start = datetime.utcnow()
        
        # Use first portion of text for analysis (to avoid token limits)
        analysis_text = extracted.content[:15000]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Generate summary (with rate limiting)
            logger.info("Waiting for rate limit before generating summary...")
            rate_limiter.wait_sync()
            summary, summary_meta = loop.run_until_complete(
                ai_service.generate_summary(analysis_text)
            )
            document.summary = summary
            total_tokens += summary_meta.get("total_tokens", 0)
            total_api_calls += 1
            
            # Extract key topics (with rate limiting)
            logger.info("Waiting for rate limit before extracting topics...")
            rate_limiter.wait_sync()
            topics, topics_meta = loop.run_until_complete(
                ai_service.extract_key_topics(analysis_text)
            )
            document.key_topics = topics
            total_tokens += topics_meta.get("total_tokens", 0)
            total_api_calls += 1
            
            # Categorize document (with rate limiting)
            logger.info("Waiting for rate limit before categorizing...")
            rate_limiter.wait_sync()
            categories, cat_meta = loop.run_until_complete(
                ai_service.categorize_document(analysis_text, summary)
            )
            document.categories = categories
            total_tokens += cat_meta.get("total_tokens", 0)
            total_api_calls += 1
            
            # Analyze sentiment (with rate limiting)
            logger.info("Waiting for rate limit before analyzing sentiment...")
            rate_limiter.wait_sync()
            sentiment, score, sent_meta = loop.run_until_complete(
                ai_service.analyze_sentiment(analysis_text)
            )
            document.sentiment = sentiment
            total_tokens += sent_meta.get("total_tokens", 0)
            total_api_calls += 1
            
            # Extract key insights (with rate limiting)
            logger.info("Waiting for rate limit before extracting insights...")
            rate_limiter.wait_sync()
            insights, insights_meta = loop.run_until_complete(
                ai_service.extract_key_insights(analysis_text, summary)
            )
            total_tokens += insights_meta.get("total_tokens", 0)
            total_api_calls += 1
            
        finally:
            loop.close()
        
        session.commit()
        
        # Save insights as separate records
        _save_insights(session, document.id, summary, insights)
        
        _record_metric(
            session, document.id, MetricType.AI_ANALYSIS,
            "ai_analysis", analysis_start, datetime.utcnow(),
            tokens=total_tokens, api_calls=total_api_calls
        )
        
        # Complete processing
        document.status = DocumentStatus.COMPLETED
        document.processing_completed_at = datetime.utcnow()
        document.processing_duration_ms = int(
            (document.processing_completed_at - document.processing_started_at).total_seconds() * 1000
        )
        session.commit()
        
        # Record overall metric
        _record_metric(
            session, document.id, MetricType.DOCUMENT_PROCESSING,
            "full_processing", start_time, datetime.utcnow(),
            tokens=total_tokens, api_calls=total_api_calls
        )
        
        logger.info(f"Successfully processed document {document_id}")
        
        return {
            "status": "completed",
            "document_id": document_id,
            "chunks": len(chunks),
            "tokens_used": total_tokens,
            "duration_ms": document.processing_duration_ms
        }
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        
        # Update document status to failed
        try:
            document = session.query(Document).filter(Document.id == UUID(document_id)).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.processing_error = str(e)
                document.processing_completed_at = datetime.utcnow()
                session.commit()
        except:
            pass
        
        # Record failure metric
        _record_metric(
            session, UUID(document_id), MetricType.DOCUMENT_PROCESSING,
            "full_processing", start_time if 'start_time' in locals() else datetime.utcnow(),
            datetime.utcnow(), success=False, error=str(e)
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    finally:
        session.close()


def _record_metric(
    session, document_id, metric_type, operation,
    started_at, completed_at, tokens=0, api_calls=0,
    success=True, error=None, metadata=None
):
    """Helper to record processing metrics."""
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    
    metric = ProcessingMetric(
        document_id=document_id,
        metric_type=metric_type,
        operation_name=operation,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        success=1 if success else 0,
        error_message=error,
        tokens_used=tokens,
        api_calls=api_calls,
        metadata=metadata or {}
    )
    session.add(metric)
    session.commit()


def _save_insights(session, document_id, summary, insights):
    """Helper to save document insights."""
    # Clear existing insights
    session.query(DocumentInsight).filter(
        DocumentInsight.document_id == document_id
    ).delete()
    
    # Save summary as insight
    session.add(DocumentInsight(
        document_id=document_id,
        insight_type="summary",
        title="Document Summary",
        content=summary,
        confidence_score=0.9
    ))
    
    # Save key points
    if insights.get("key_points"):
        session.add(DocumentInsight(
            document_id=document_id,
            insight_type="key_points",
            title="Key Points",
            content=json.dumps({"key_points": insights["key_points"]}),
            confidence_score=0.85
        ))
    
    # Save entities
    if insights.get("entities"):
        session.add(DocumentInsight(
            document_id=document_id,
            insight_type="entities",
            title="Named Entities",
            content=json.dumps({"entities": insights["entities"]}),
            confidence_score=0.8
        ))
    
    # Save action items
    if insights.get("action_items"):
        session.add(DocumentInsight(
            document_id=document_id,
            insight_type="action_items",
            title="Action Items",
            content=json.dumps({"action_items": insights["action_items"]}),
            confidence_score=0.75
        ))
    
    session.commit()

