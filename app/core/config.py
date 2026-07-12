"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Provider Selection
    llm_provider: str = "openrouter"  # Options: "gemini", "mancer", or "openrouter"
    
    # Gemini API Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-pro"
    
    # Mancer API Configuration
    mancer_api_key: Optional[str] = None
    mancer_base_url: str = "https://neuro.mancer.tech/oai/v1"
    mancer_default_model: str = "mytholite"
    
    # OpenRouter API Configuration
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "google/gemma-2-9b-it:free"
    openrouter_site_url: Optional[str] = None
    openrouter_site_name: Optional[str] = None
    # Enable OpenRouter's built-in web search plugin so characters can research
    # live info. Runs a web search on relevant queries (adds cost/latency per
    # message). Set OPENROUTER_WEB_SEARCH=false in .env to disable.
    openrouter_web_search: bool = True

    # OpenAI API Configuration (used for embeddings)
    openai_api_key: Optional[str] = None
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Memory Configuration
    max_working_memory_size: int = 20
    summarize_after_messages: int = 20
    db_path: str = "./data/sessions"
    
    # RAG Configuration
    embedding_provider: str = "openai"  # "openai" or "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    rag_top_k: int = 3
    
    # Phase 2: Feature Flags
    enable_chromadb: bool = True
    store_chat_embeddings: bool = True  # Set False to stop writing new embeddings (saves space)
    ingest_knowledge_base: bool = True  # Set False to disable knowledge_base ingestion on startup
    reset_ingestion_on_start: bool = False  # Set True to delete manifest and force full re-ingest on every startup
    enable_reranking: bool = False
    enable_transformer_emotions: bool = False
    enable_redis: bool = False
    enable_postgresql: bool = False
    enable_metrics: bool = False
    enable_notion_tools: bool = False  # Let characters call Notion MCP tools (search/read/create)
    notion_tool_max_iters: int = 5     # Max tool-call rounds per response
    notion_default_parent_id: str = ""  # Notion data_source/database id new pages are created under

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

    # Conversation history is controlled SOLELY by message count, not token budget.
    # We send the last N messages verbatim. Keeping this small keeps every request
    # tiny and cheap (the previous token-budget approach let history grow to ~60k
    # tokens/call, which dominated cost). history_token_percent above no longer
    # governs history length — it is retained only for legacy budget accounting.
    history_message_limit: int = 6

    # Prompt Caching (Anthropic/Claude via OpenRouter)
    # Adds cache_control breakpoints to the stable prompt prefix (character card +
    # conversation history). No-op for non-Claude models. TTL options: "5m" or "1h".
    prompt_cache_enabled: bool = True
    prompt_cache_ttl: str = "1h"

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Computed Properties
    @property
    def max_context_tokens(self) -> int:
        """Maximum tokens for entire context (provider-dependent)."""
        if self.llm_provider == "mancer":
            # Most Mancer models have 4k-8k context
            return 8000
        elif self.llm_provider == "openrouter":
            # Claude Opus 4.x via OpenRouter has a 1M context window. We cap well
            # below that: enough to keep conversation history append-only (stable,
            # cacheable prefix) and give characters long memory, without sending
            # the entire 1M every turn. History/RAG split is tuned via *_token_percent.
            return 150000
        else:
            # Gemini 1.5 Pro has 128k context window
            return 128000
    
    @property
    def max_response_tokens(self) -> int:
        """Maximum tokens for model response (provider-dependent)."""
        if self.llm_provider == "mancer":
            # Most Mancer models have 2k-4k max output
            return 2048
        elif self.llm_provider == "openrouter":
            # OpenRouter free tier models typically 2k max output
            return 4096
        else:
            # Gemini 1.5 Pro max output
            return 8192
    
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
