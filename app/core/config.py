"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Gemini API Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-pro"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Memory Configuration
    max_working_memory_size: int = 20
    summarize_after_messages: int = 20
    db_path: str = "./data/sessions"
    
    # RAG Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    rag_top_k: int = 3
    use_chromadb: bool = False
    
    # Token Budget (percentage allocation)
    system_token_percent: int = 20
    rag_token_percent: int = 25
    history_token_percent: int = 35
    response_token_percent: int = 20
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Computed Properties
    @property
    def max_context_tokens(self) -> int:
        """Maximum tokens for entire context (Gemini 1.5 Pro limit)."""
        return 128000  # Gemini 1.5 Pro has 128k context window
    
    @property
    def max_response_tokens(self) -> int:
        """Maximum tokens for model response."""
        return 8192  # Gemini 1.5 Pro max output
    
    @property
    def system_token_budget(self) -> int:
        """Token budget for system/persona content."""
        return int(self.max_context_tokens * self.system_token_percent / 100)
    
    @property
    def rag_token_budget(self) -> int:
        """Token budget for RAG retrieved context."""
        return int(self.max_context_tokens * self.rag_token_percent / 100)
    
    @property
    def history_token_budget(self) -> int:
        """Token budget for conversation history."""
        return int(self.max_context_tokens * self.history_token_percent / 100)
    
    @property
    def response_token_budget(self) -> int:
        """Token budget for model response."""
        return int(self.max_context_tokens * self.response_token_percent / 100)
    
    def ensure_data_directories(self) -> None:
        """Create data directories if they don't exist."""
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        Path("./data/embeddings").mkdir(parents=True, exist_ok=True)
        Path("./logs").mkdir(parents=True, exist_ok=True)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
settings.ensure_data_directories()
