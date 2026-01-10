"""Tests for service layer."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.document_processor import DocumentProcessor, ExtractedText, TextChunk
from app.services.storage import StorageService


class TestDocumentProcessor:
    """Tests for document processing service."""
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        processor = DocumentProcessor()
        processor.chunk_size = 100
        processor.chunk_overlap = 20
        
        extracted = ExtractedText(
            content="This is a test paragraph.\n\nThis is another paragraph with more content.",
            page_count=1,
            word_count=12,
            character_count=70,
            pages=[{
                "page_number": 1,
                "content": "This is a test paragraph.\n\nThis is another paragraph with more content."
            }],
            metadata={}
        )
        
        chunks = processor.chunk_text(extracted)
        
        assert len(chunks) > 0
        assert all(isinstance(c, TextChunk) for c in chunks)
        assert all(c.chunk_index >= 0 for c in chunks)
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        processor = DocumentProcessor()
        
        text = "This is a test sentence with approximately forty characters."
        tokens = processor._estimate_tokens(text)
        
        # Rough estimate: ~4 chars per token
        assert tokens > 0
        assert tokens < len(text)
    
    def test_split_into_paragraphs(self):
        """Test paragraph splitting."""
        processor = DocumentProcessor()
        
        text = "Paragraph one.\n\nParagraph two.\n\n\nParagraph three."
        paragraphs = processor._split_into_paragraphs(text)
        
        assert len(paragraphs) == 3
        assert paragraphs[0] == "Paragraph one."


class TestStorageService:
    """Tests for storage service."""
    
    def test_validate_file_type_valid(self):
        """Test validation of allowed file types."""
        storage = StorageService()
        
        assert storage.validate_file_type("document.pdf") is True
        assert storage.validate_file_type("document.docx") is True
        assert storage.validate_file_type("document.txt") is True
        assert storage.validate_file_type("document.md") is True
    
    def test_validate_file_type_invalid(self):
        """Test validation of disallowed file types."""
        storage = StorageService()
        
        assert storage.validate_file_type("document.exe") is False
        assert storage.validate_file_type("document.zip") is False
        assert storage.validate_file_type("document.js") is False
    
    def test_get_file_type(self):
        """Test file type extraction."""
        storage = StorageService()
        
        assert storage.get_file_type("document.pdf") == "pdf"
        assert storage.get_file_type("document.DOCX") == "docx"
        assert storage.get_file_type("path/to/file.txt") == "txt"
    
    def test_generate_filename(self):
        """Test unique filename generation."""
        storage = StorageService()
        
        filename1 = storage._generate_filename("test.pdf")
        filename2 = storage._generate_filename("test.pdf")
        
        # Should be unique
        assert filename1 != filename2
        # Should preserve extension
        assert filename1.endswith(".pdf")
        assert filename2.endswith(".pdf")
    
    def test_get_file_hash(self):
        """Test file hash generation."""
        storage = StorageService()
        
        content = b"test content"
        hash1 = storage.get_file_hash(content)
        hash2 = storage.get_file_hash(content)
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars

