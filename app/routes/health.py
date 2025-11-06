"""Health check endpoint."""

import logging
from fastapi import APIRouter, Depends
from app.models.chat import HealthResponse

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
        memory_manager
    )
    
    try:
        # Check Gemini API connection
        gemini_healthy = await gemini_client.check_connection()
        
        # Check database
        db_healthy = memory_manager.check_db_connection()
        
        # Count active sessions
        active_sessions = len(memory_manager.active_sessions)
        
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
