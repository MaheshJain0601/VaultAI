"""Application configuration using pydantic-settings."""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database (Supabase or Local PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vault_ai"
    sync_database_url: str = "postgresql://postgres:postgres@localhost:5432/vault_ai"
    
    # Supabase Configuration (for database features, not storage)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None  # Anon key
    supabase_service_key: Optional[str] = None  # Service role key
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Google Gemini AI
    google_api_key: str = ""
    
    # Local Storage (only local storage is supported)
    storage_path: str = "./storage/documents"
    
    # Application
    app_name: str = "Vault AI"
    app_version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Processing
    max_file_size_mb: int = 50
    allowed_extensions: str = "pdf,docx,txt,md"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # AI Settings (Google Gemini)
    embedding_model: str = "models/text-embedding-004"
    chat_model: str = "gemini-2.0-flash"
    max_context_tokens: int = 4000
    temperature: float = 0.1
    
    # Rate Limiting (requests per minute to LLM API)
    llm_requests_per_minute: int = 10  # Default: 10 requests per minute
    
    # Feature Flags
    enable_pgvector: bool = True
    reset_db_on_startup: bool = False  # WARNING: When enabled, drops all tables on startup
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions into a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured."""
        return bool(self.supabase_url and self.supabase_key)
    
    @property
    def is_using_supabase_db(self) -> bool:
        """Check if using Supabase for database."""
        return "supabase" in self.database_url.lower()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
