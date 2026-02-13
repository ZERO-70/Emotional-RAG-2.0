"""Health check and metrics endpoints."""

import logging
from fastapi import APIRouter, Response
from app.models.chat import HealthResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns system health status including:
    - API status
    - LLM provider connection (Gemini/Mancer/OpenRouter)
    - Database status
    - Active memory sessions
    """
    from app.main import (
        gemini_client,
        memory_manager,
        chromadb_store,
        redis_memory,
        metrics_collector
    )
    
    try:
        # Check LLM provider connection
        llm_healthy = await gemini_client.check_connection()
        
        # Check database
        db_healthy = memory_manager.check_db_connection()
        
        # Count active sessions
        active_sessions = len(memory_manager.active_sessions)
        
        # Phase 2: Update metrics
        if settings.enable_metrics and metrics_collector:
            metrics_collector.update_active_sessions(active_sessions)
        
        status = "healthy" if (llm_healthy and db_healthy) else "degraded"
        
        logger.info(
            f"Health check: {status}",
            extra={
                "llm_provider": settings.llm_provider,
                "llm_api": llm_healthy,
                "database": db_healthy,
                "active_sessions": active_sessions
            }
        )
        
        # Build response with provider-specific status
        response_data = {
            "status": status,
            "database": db_healthy,
            "memory_sessions": active_sessions,
            "llm_provider": settings.llm_provider
        }
        
        # Set provider-specific API status
        if settings.llm_provider == "gemini":
            response_data["gemini_api"] = llm_healthy
            response_data["mancer_api"] = False
            response_data["openrouter_api"] = False
        elif settings.llm_provider == "mancer":
            response_data["gemini_api"] = False
            response_data["mancer_api"] = llm_healthy
            response_data["openrouter_api"] = False
        elif settings.llm_provider == "openrouter":
            response_data["gemini_api"] = False
            response_data["mancer_api"] = False
            response_data["openrouter_api"] = llm_healthy
        
        return HealthResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="unhealthy",
            gemini_api=False,
            database=False,
            memory_sessions=0
        )


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    Only available if ENABLE_METRICS=true.
    """
    from app.main import metrics_collector
    
    if not settings.enable_metrics:
        return Response(
            content="Metrics not enabled. Set ENABLE_METRICS=true in .env",
            media_type="text/plain",
            status_code=404
        )
    
    if not metrics_collector:
        return Response(
            content="Metrics collector not initialized",
            media_type="text/plain",
            status_code=500
        )
    
    metrics_data = metrics_collector.get_metrics()
    content_type = metrics_collector.get_content_type()
    
    return Response(
        content=metrics_data,
        media_type=content_type
    )
