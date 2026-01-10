"""Tests for document management API."""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


class TestDocumentUpload:
    """Tests for document upload functionality."""
    
    @pytest.mark.asyncio
    async def test_upload_document_success(
        self, client: AsyncClient, sample_text_content: bytes
    ):
        """Test successful document upload."""
        with patch("app.api.documents.process_document_task") as mock_task:
            mock_task.delay = AsyncMock()
            
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.txt", sample_text_content, "text/plain")},
                data={"title": "Test Document", "description": "A test document"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["filename"] == "test.txt"
        assert data["file_type"] == "txt"
        assert data["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_upload_document_invalid_type(self, client: AsyncClient):
        """Test upload with invalid file type."""
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.exe", b"invalid content", "application/octet-stream")}
        )
        
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_upload_document_too_large(self, client: AsyncClient):
        """Test upload with file that's too large."""
        # Create content larger than max size
        large_content = b"x" * (51 * 1024 * 1024)  # 51 MB
        
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.txt", large_content, "text/plain")}
        )
        
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()


class TestDocumentList:
    """Tests for document listing functionality."""
    
    @pytest.mark.asyncio
    async def test_list_documents_empty(self, client: AsyncClient):
        """Test listing when no documents exist."""
        response = await client.get("/api/v1/documents/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, client: AsyncClient):
        """Test pagination parameters."""
        response = await client.get(
            "/api/v1/documents/",
            params={"page": 1, "page_size": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data


class TestDocumentRetrieval:
    """Tests for document retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client: AsyncClient):
        """Test getting a non-existent document."""
        response = await client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000"
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_document_status_not_found(self, client: AsyncClient):
        """Test getting status of non-existent document."""
        response = await client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000/status"
        )
        
        assert response.status_code == 404


class TestDocumentDeletion:
    """Tests for document deletion functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, client: AsyncClient):
        """Test deleting a non-existent document."""
        response = await client.delete(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000"
        )
        
        assert response.status_code == 404

