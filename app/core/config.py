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
    
    # Phase 2: Feature Flags
    enable_chromadb: bool = False
    enable_reranking: bool = False
    enable_transformer_emotions: bool = False
    enable_redis: bool = False
    enable_postgresql: bool = False
    enable_metrics: bool = False
    
    # Phase 2: ChromaDB Configuration
    chromadb_path: str = "./data/chromadb"
    chromadb_host: Optional[str] = None
    chromadb_port: Optional[int] = None
    
    # Phase 2: Reranking Configuration
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranking_candidates: int = 50
    reranking_top_k: int = 10
    
    # Phase 2: Advanced Emotion Detection
    emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    emotion_confidence_threshold: float = 0.5
    
    # Phase 2: Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl: int = 1800  # 30 minutes
    redis_max_connections: int = 10
    
    # Phase 2: PostgreSQL Configuration
    postgres_url: Optional[str] = None
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20
    
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
        
        # Phase 2 directories
        if self.enable_chromadb:
            Path(self.chromadb_path).mkdir(parents=True, exist_ok=True)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
settings.ensure_data_directories()
