"""Chat API endpoints for document Q&A."""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.document import Document, DocumentStatus
from app.models.chat import ChatSession, ChatMessage, MessageRole
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatHistoryResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    Citation,
    MultiDocumentChatRequest,
    MultiDocumentChatResponse
)
from app.services.rag_service import rag_service

router = APIRouter()


@router.post("/sessions", response_model=ChatSessionResponse)
async def start_chat_session(
    request: ChatSessionCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Start a new chat session for a document.
    
    Creates a conversation context that maintains history for multi-turn
    interactions. Each session is tied to a document (or multiple documents
    for multi-doc chat).
    """
    # Verify document exists and is processed
    result = await db.execute(
        select(Document).where(Document.id == request.document_id)
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready for chat. Current status: {document.status.value}"
        )
    
    # Create session
    session = ChatSession(
        document_id=request.document_id,
        title=request.title or f"Chat about {document.original_filename}",
        context_window=request.context_window,
        document_ids=[request.document_id] + request.additional_document_ids
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    document_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session)
):
    """List chat sessions with optional filtering."""
    query = select(ChatSession)
    
    if document_id:
        query = query.where(ChatSession.document_id == document_id)
    
    if active_only:
        query = query.where(ChatSession.is_active == True)
    
    offset = (page - 1) * page_size
    query = query.order_by(ChatSession.updated_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return [ChatSessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Get chat session details."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get chat history for a session.
    
    Returns all messages in chronological order with pagination.
    Includes citations for assistant responses.
    """
    # Get session
    session_result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = session_result.scalar()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get total message count
    count_result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    )
    total_messages = count_result.scalar()
    
    # Get messages with pagination
    offset = (page - 1) * page_size
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .offset(offset)
        .limit(page_size)
    )
    messages = messages_result.scalars().all()
    
    # Convert to response format
    message_responses = []
    for msg in messages:
        citations = [Citation(**c) for c in (msg.citations or [])]
        response = ChatMessageResponse(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role.value,
            content=msg.content,
            citations=citations,
            prompt_tokens=msg.prompt_tokens or 0,
            completion_tokens=msg.completion_tokens or 0,
            total_tokens=msg.total_tokens or 0,
            model_used=msg.model_used,
            response_time_ms=msg.response_time_ms,
            confidence_score=msg.confidence_score,
            suggested_questions=msg.suggested_questions or [],
            created_at=msg.created_at
        )
        message_responses.append(response)
    
    return ChatHistoryResponse(
        session=ChatSessionResponse.model_validate(session),
        messages=message_responses,
        total_messages=total_messages
    )


@router.post("/sessions/{session_id}/ask", response_model=AskQuestionResponse)
async def ask_question(
    session_id: uuid.UUID,
    request: AskQuestionRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Ask a question about the document in a chat session.
    
    Uses RAG (Retrieval-Augmented Generation) to:
    1. Find relevant document sections using semantic search
    2. Build context from the most relevant chunks
    3. Generate an accurate answer with source citations
    4. Suggest follow-up questions
    
    Multi-turn context is maintained - the model has access to recent
    conversation history for coherent follow-up responses.
    """
    # Get session
    session_result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = session_result.scalar()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    if not session.is_active:
        raise HTTPException(status_code=400, detail="Chat session is closed")
    
    # Save user message
    user_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        content=request.question
    )
    db.add(user_message)
    await db.flush()
    
    # Generate answer using RAG
    answer_data = await rag_service.answer_question(
        db=db,
        session=session,
        question=request.question,
        num_context_chunks=request.num_context_chunks,
        similarity_threshold=request.similarity_threshold,
        include_citations=request.include_citations,
        include_suggestions=request.include_suggestions,
        max_response_tokens=request.max_response_tokens
    )
    
    # Save assistant message
    assistant_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=answer_data["answer"],
        citations=answer_data["citations"],
        context_chunks=[c["chunk_id"] for c in answer_data["citations"]],
        prompt_tokens=answer_data["prompt_tokens"],
        completion_tokens=answer_data["completion_tokens"],
        total_tokens=answer_data["total_tokens"],
        model_used=answer_data["model_used"],
        response_time_ms=answer_data["response_time_ms"],
        suggested_questions=answer_data["suggestions"]
    )
    db.add(assistant_message)
    
    # Update session stats
    session.message_count += 2
    session.total_tokens_used += answer_data["total_tokens"]
    session.last_message_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(assistant_message)
    
    # Build response
    citations = [
        Citation(
            chunk_id=uuid.UUID(c["chunk_id"]),
            content_snippet=c["content_snippet"],
            page_number=c.get("page_number"),
            relevance_score=c["relevance_score"]
        )
        for c in answer_data["citations"]
    ]
    
    message_response = ChatMessageResponse(
        id=assistant_message.id,
        session_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content=answer_data["answer"],
        citations=citations,
        prompt_tokens=answer_data["prompt_tokens"],
        completion_tokens=answer_data["completion_tokens"],
        total_tokens=answer_data["total_tokens"],
        model_used=answer_data["model_used"],
        response_time_ms=answer_data["response_time_ms"],
        suggested_questions=answer_data["suggestions"],
        created_at=assistant_message.created_at
    )
    
    return AskQuestionResponse(
        message=message_response,
        citations=citations,
        suggested_questions=answer_data["suggestions"],
        context_used=answer_data["context_used"],
        response_time_ms=answer_data["response_time_ms"]
    )


@router.post("/multi-document", response_model=MultiDocumentChatResponse)
async def multi_document_chat(
    request: MultiDocumentChatRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Ask a question across multiple documents (Bonus Feature).
    
    Retrieves relevant context from all specified documents and
    synthesizes an answer that draws from multiple sources.
    Useful for comparing information or finding patterns across documents.
    """
    # Verify all documents exist and are processed
    for doc_id in request.document_ids:
        result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        document = result.scalar()
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        if document.status != DocumentStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Document {doc_id} not ready for chat"
            )
    
    # Get multi-document answer
    answer_data = await rag_service.answer_multi_document_question(
        db=db,
        document_ids=request.document_ids,
        question=request.question,
        num_chunks_per_doc=request.num_context_chunks_per_doc
    )
    
    citations = [
        Citation(
            chunk_id=uuid.UUID(c["chunk_id"]),
            content_snippet=c["content_snippet"],
            page_number=c.get("page_number"),
            relevance_score=c["relevance_score"]
        )
        for c in answer_data["citations"]
    ]
    
    return MultiDocumentChatResponse(
        answer=answer_data["answer"],
        citations=citations,
        documents_used=[uuid.UUID(d) for d in answer_data["documents_used"]],
        suggested_questions=[],
        response_time_ms=answer_data["response_time_ms"]
    )


@router.delete("/sessions/{session_id}")
async def close_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Close a chat session (soft delete - marks as inactive)."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    session.is_active = False
    await db.commit()
    
    return {"message": "Chat session closed", "id": str(session_id)}


@router.delete("/sessions/{session_id}/permanent")
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Permanently delete a chat session and all messages."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    await db.delete(session)
    await db.commit()
    
    return {"message": "Chat session deleted", "id": str(session_id)}

