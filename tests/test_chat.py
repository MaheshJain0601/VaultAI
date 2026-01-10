"""Tests for chat API."""
import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestChatSession:
    """Tests for chat session management."""
    
    @pytest.mark.asyncio
    async def test_create_session_document_not_found(self, client: AsyncClient):
        """Test creating session for non-existent document."""
        response = await client.post(
            "/api/v1/chat/sessions",
            json={
                "document_id": str(uuid4()),
                "title": "Test Chat"
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client: AsyncClient):
        """Test listing sessions when none exist."""
        response = await client.get("/api/v1/chat/sessions")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client: AsyncClient):
        """Test getting non-existent session."""
        response = await client.get(
            f"/api/v1/chat/sessions/{uuid4()}"
        )
        
        assert response.status_code == 404


class TestChatHistory:
    """Tests for chat history functionality."""
    
    @pytest.mark.asyncio
    async def test_get_history_session_not_found(self, client: AsyncClient):
        """Test getting history for non-existent session."""
        response = await client.get(
            f"/api/v1/chat/sessions/{uuid4()}/history"
        )
        
        assert response.status_code == 404


class TestAskQuestion:
    """Tests for question-answering functionality."""
    
    @pytest.mark.asyncio
    async def test_ask_question_session_not_found(self, client: AsyncClient):
        """Test asking question in non-existent session."""
        response = await client.post(
            f"/api/v1/chat/sessions/{uuid4()}/ask",
            json={"question": "What is this document about?"}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_ask_question_validation(self, client: AsyncClient):
        """Test question validation."""
        response = await client.post(
            f"/api/v1/chat/sessions/{uuid4()}/ask",
            json={"question": ""}  # Empty question
        )
        
        # Should fail validation
        assert response.status_code == 422


class TestMultiDocumentChat:
    """Tests for multi-document chat functionality."""
    
    @pytest.mark.asyncio
    async def test_multi_document_chat_empty_list(self, client: AsyncClient):
        """Test multi-document chat with empty document list."""
        response = await client.post(
            "/api/v1/chat/multi-document",
            json={
                "question": "What do these documents say?",
                "document_ids": []
            }
        )
        
        # Should fail validation (min 1 document)
        assert response.status_code == 422

