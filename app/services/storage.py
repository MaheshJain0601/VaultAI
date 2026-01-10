"""Storage service for local file management."""
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Tuple
import aiofiles
import aiofiles.os

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for handling local file storage operations.
    
    Stores documents in the local filesystem for processing.
    Files are organized in the configured storage path with
    unique generated filenames.
    """
    
    def __init__(self):
        self.storage_path = Path(settings.storage_path)
    
    async def initialize(self):
        """Create storage directory if it doesn't exist."""
        await aiofiles.os.makedirs(self.storage_path, exist_ok=True)
        logger.info(f"Storage initialized at: {self.storage_path}")
    
    def _generate_filename(self, original_filename: str) -> str:
        """Generate a unique filename while preserving extension."""
        ext = Path(original_filename).suffix.lower()
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{ext}"
    
    def _get_file_path(self, filename: str) -> Path:
        """Get full path for a file."""
        return self.storage_path / filename
    
    async def save_file(
        self, 
        file_content: bytes, 
        original_filename: str
    ) -> Tuple[str, str, int]:
        """
        Save file to local storage.
        
        Args:
            file_content: Raw file bytes
            original_filename: Original name of the uploaded file
            
        Returns:
            Tuple of (generated_filename, file_path, file_size)
        """
        await self.initialize()
        
        generated_filename = self._generate_filename(original_filename)
        file_path = self._get_file_path(generated_filename)
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        
        file_size = len(file_content)
        logger.info(f"Saved file: {generated_filename} ({file_size} bytes)")
        
        return generated_filename, str(file_path), file_size
    
    async def get_file(self, filename: str) -> Optional[bytes]:
        """Read file from local storage."""
        file_path = self._get_file_path(filename)
        
        if not await aiofiles.os.path.exists(file_path):
            logger.warning(f"File not found: {filename}")
            return None
        
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()
    
    async def delete_file(self, filename: str) -> bool:
        """Delete file from local storage."""
        file_path = self._get_file_path(filename)
        
        try:
            if await aiofiles.os.path.exists(file_path):
                await aiofiles.os.remove(file_path)
                logger.info(f"Deleted file: {filename}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete file {filename}: {e}")
        return False
    
    async def file_exists(self, filename: str) -> bool:
        """Check if file exists in local storage."""
        file_path = self._get_file_path(filename)
        return await aiofiles.os.path.exists(file_path)
    
    def get_file_sync(self, filename: str) -> Optional[bytes]:
        """
        Read file synchronously (for Celery workers).
        
        Celery workers run synchronously, so they need a sync method
        to read files for processing.
        """
        file_path = self._get_file_path(filename)
        
        if not file_path.exists():
            return None
        
        with open(file_path, "rb") as f:
            return f.read()
    
    def get_file_hash(self, file_content: bytes) -> str:
        """Generate SHA-256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()
    
    def validate_file_type(self, filename: str) -> bool:
        """Validate if file type is allowed."""
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in settings.allowed_extensions_list
    
    def validate_file_size(self, file_size: int) -> bool:
        """Validate if file size is within limits."""
        return file_size <= settings.max_file_size_bytes
    
    def get_file_type(self, filename: str) -> str:
        """Get file type from filename."""
        return Path(filename).suffix.lower().lstrip(".")
    
    @property
    def max_file_size_mb(self) -> int:
        """Get max file size in MB."""
        return settings.max_file_size_mb
    
    @property
    def allowed_extensions_list(self) -> list:
        """Get list of allowed extensions."""
        return settings.allowed_extensions_list


# Singleton instance
storage_service = StorageService()
