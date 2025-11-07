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
    - Gemini API connection
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
        # Check Gemini API connection
        gemini_healthy = await gemini_client.check_connection()
        
        # Check database
        db_healthy = memory_manager.check_db_connection()
        
        # Count active sessions
        active_sessions = len(memory_manager.active_sessions)
        
        # Phase 2: Update metrics
        if settings.enable_metrics and metrics_collector:
            metrics_collector.update_active_sessions(active_sessions)
        
        status = "healthy" if (gemini_healthy and db_healthy) else "degraded"
        
        logger.info(
            f"Health check: {status}",
            extra={
                "gemini_api": gemini_healthy,
                "database": db_healthy,
                "active_sessions": active_sessions
            }
        )
        
        return HealthResponse(
            status=status,
            gemini_api=gemini_healthy,
            database=db_healthy,
            memory_sessions=active_sessions
        )
        
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
