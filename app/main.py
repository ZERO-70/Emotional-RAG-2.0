"""FastAPI application initialization with dependency injection."""

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.core.memory import MemoryManager
from app.core.token_manager import TokenManager
from app.services.gemini_client import GeminiClient
from app.services.mancer_client import MancerClient
from app.services.llm_provider import UnifiedLLMClient
from app.services.rag_engine import RAGEngine
from app.services.emotion_tracker import EmotionTracker
from app.routes import chat, health

# Phase 2 imports (conditional)
if settings.enable_chromadb:
    from app.services.chromadb_store import ChromaDBVectorStore
    
if settings.enable_reranking:
    from app.services.reranker import Reranker
    
if settings.enable_transformer_emotions:
    from app.services.transformer_emotions import TransformerEmotionDetector
    
if settings.enable_redis:
    from app.services.redis_memory import RedisMemoryStore
    
if settings.enable_metrics:
    from app.services.metrics import MetricsCollector

# Configure logging
def setup_logging():
    """Configure structured JSON logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if settings.log_format == "json":
        # JSON formatter
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            rename_fields={"levelname": "level", "asctime": "timestamp"}
        )
    else:
        # Standard formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# Global service instances
llm_client: UnifiedLLMClient = None  # Unified client (replaces gemini_client)
gemini_client = None  # Kept for backward compatibility
rag_engine: RAGEngine = None
emotion_tracker: EmotionTracker = None
token_manager: TokenManager = None
memory_manager: MemoryManager = None

# Phase 2 service instances (conditional)
chromadb_store = None
reranker = None
transformer_emotion_detector = None
redis_memory = None
metrics_collector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown:
    - Initialize services
    - Load models
    - Clean up connections
    """
    global llm_client, gemini_client, rag_engine, emotion_tracker, token_manager, memory_manager
    global chromadb_store, reranker, transformer_emotion_detector, redis_memory, metrics_collector
    
    logger.info("Starting Emotional RAG Backend...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Phase 2 features: ChromaDB={settings.enable_chromadb}, Reranking={settings.enable_reranking}, "
                f"Transformer Emotions={settings.enable_transformer_emotions}, Redis={settings.enable_redis}, "
                f"PostgreSQL={settings.enable_postgresql}, Metrics={settings.enable_metrics}")
    
    # Startup
    try:
        # Initialize services
        logger.info("Initializing core services...")
        
        # Initialize the appropriate LLM provider
        if settings.llm_provider == "mancer":
            logger.info("Initializing Mancer API client...")
            if not settings.mancer_api_key:
                raise ValueError("MANCER_API_KEY is required when llm_provider=mancer")
            
            mancer_provider = MancerClient()
            llm_client = UnifiedLLMClient(mancer_provider, "mancer")
            gemini_client = llm_client  # Backward compatibility alias
            
        elif settings.llm_provider == "openrouter":
            logger.info("Initializing OpenRouter API client...")
            if not settings.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY is required when llm_provider=openrouter")
            
            from app.services.openrouter_client import OpenRouterClient
            openrouter_provider = OpenRouterClient()
            llm_client = UnifiedLLMClient(openrouter_provider, "openrouter")
            gemini_client = llm_client  # Backward compatibility alias
            
        elif settings.llm_provider == "gemini":
            logger.info("Initializing Gemini API client...")
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required when llm_provider=gemini")
            
            gemini_provider = GeminiClient()
            llm_client = UnifiedLLMClient(gemini_provider, "gemini")
            gemini_client = llm_client  # Backward compatibility alias
            
        else:
            raise ValueError(f"Invalid llm_provider: {settings.llm_provider}. Must be 'gemini', 'mancer', or 'openrouter'")
        
        rag_engine = RAGEngine()
        emotion_tracker = EmotionTracker()
        token_manager = TokenManager()
        
        # Phase 2: Initialize optional services
        if settings.enable_chromadb:
            logger.info("Initializing ChromaDB vector store...")
            chromadb_store = ChromaDBVectorStore()
        
        if settings.enable_reranking:
            logger.info("Loading cross-encoder reranker...")
            reranker = Reranker()
        
        if settings.enable_transformer_emotions:
            logger.info("Loading transformer emotion detector...")
            transformer_emotion_detector = TransformerEmotionDetector()
        
        if settings.enable_redis:
            logger.info("Connecting to Redis...")
            redis_memory = RedisMemoryStore()
            await redis_memory.connect()
        
        if settings.enable_metrics:
            logger.info("Initializing Prometheus metrics...")
            metrics_collector = MetricsCollector()
        
        memory_manager = MemoryManager(
            rag_engine=rag_engine,
            emotion_tracker=emotion_tracker,
            token_manager=token_manager,
            chromadb_store=chromadb_store if settings.enable_chromadb else None
        )
        
        logger.info("All services initialized successfully")
        
        # Test LLM provider connection
        if settings.llm_provider == "gemini":
            gemini_ok = await llm_client.check_connection()
            if gemini_ok:
                logger.info("GEMINI API connection verified")
            else:
                logger.warning("GEMINI API connection check failed - continuing anyway")
        elif settings.llm_provider == "mancer":
            mancer_ok = await llm_client.check_connection()
            if mancer_ok:
                logger.info("MANCER API connection verified")
            else:
                logger.warning("MANCER API connection check failed - continuing anyway")
        elif settings.llm_provider == "openrouter":
            openrouter_ok = await llm_client.check_connection()
            if openrouter_ok:
                logger.info("OPENROUTER API connection verified")
            else:
                logger.warning("OPENROUTER API connection check failed - continuing anyway")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        if memory_manager:
            await memory_manager.close_all()
        
        # Close LLM client
        if llm_client:
            await llm_client.close()
        
        # Phase 2: Cleanup
        if redis_memory:
            await redis_memory.close()
        
        if chromadb_store:
            await chromadb_store.close()
        
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


# Create FastAPI app
app = FastAPI(
    title="Emotional RAG Backend",
    description="Production-ready backend for SillyTavern with proactive memory management - Phase 2 with advanced features",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for SillyTavern
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify SillyTavern origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat.router, tags=["chat"])
app.include_router(health.router, tags=["health"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Emotional RAG Backend",
        "version": "2.0.0",
        "phase": "2",
        "status": "running",
        "features": {
            "chromadb": settings.enable_chromadb,
            "reranking": settings.enable_reranking,
            "transformer_emotions": settings.enable_transformer_emotions,
            "redis": settings.enable_redis,
            "postgresql": settings.enable_postgresql,
            "metrics": settings.enable_metrics
        },
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "error": str(exc),
        "type": type(exc).__name__
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
