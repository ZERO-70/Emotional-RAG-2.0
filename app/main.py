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
from app.services.rag_engine import RAGEngine
from app.services.emotion_tracker import EmotionTracker
from app.routes import chat, health

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
gemini_client: GeminiClient = None
rag_engine: RAGEngine = None
emotion_tracker: EmotionTracker = None
token_manager: TokenManager = None
memory_manager: MemoryManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown:
    - Initialize services
    - Load models
    - Clean up connections
    """
    global gemini_client, rag_engine, emotion_tracker, token_manager, memory_manager
    
    logger.info("Starting Emotional RAG Backend...")
    
    # Startup
    try:
        # Initialize services
        logger.info("Initializing services...")
        
        gemini_client = GeminiClient()
        rag_engine = RAGEngine()
        emotion_tracker = EmotionTracker()
        token_manager = TokenManager()
        
        memory_manager = MemoryManager(
            rag_engine=rag_engine,
            emotion_tracker=emotion_tracker,
            token_manager=token_manager
        )
        
        logger.info("All services initialized successfully")
        
        # Test Gemini connection
        gemini_healthy = await gemini_client.check_connection()
        if not gemini_healthy:
            logger.warning("Gemini API connection check failed - check your API key")
        else:
            logger.info("Gemini API connection verified")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        if memory_manager:
            await memory_manager.close_all()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


# Create FastAPI app
app = FastAPI(
    title="Emotional RAG Backend",
    description="Production-ready backend for SillyTavern with proactive memory management",
    version="1.0.0",
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
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "health": "/health",
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
