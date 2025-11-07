"""Prometheus metrics for monitoring and observability.

Phase 2 enhancement providing:
- Request counters and latency histograms
- Token usage tracking
- Emotion distribution metrics
- RAG retrieval metrics
"""

import logging
from typing import Optional
from functools import wraps
import time

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = Info = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Prometheus metrics collection for application monitoring.
    
    Tracks:
    - Request counts and latencies
    - Token usage and budgets
    - Emotion distribution
    - RAG retrieval performance
    - Error rates
    """
    
    def __init__(self):
        """Initialize Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                "prometheus_client not available. "
                "Install with: pip install prometheus-client>=0.19.0"
            )
            self.enabled = False
            return
        
        self.enabled = True
        
        # Request metrics
        self.request_count = Counter(
            'chat_requests_total',
            'Total number of chat requests',
            ['endpoint', 'status']
        )
        
        self.request_latency = Histogram(
            'chat_request_duration_seconds',
            'Chat request latency in seconds',
            ['endpoint'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # Token usage metrics
        self.tokens_used = Counter(
            'tokens_used_total',
            'Total tokens consumed',
            ['type']  # prompt, completion, total
        )
        
        self.context_tokens = Histogram(
            'context_tokens',
            'Token count in context',
            ['component'],  # system, rag, history
            buckets=[100, 500, 1000, 5000, 10000, 20000, 50000]
        )
        
        # Emotion metrics
        self.emotion_count = Counter(
            'emotions_detected_total',
            'Count of emotions detected',
            ['emotion']
        )
        
        self.emotion_confidence = Histogram(
            'emotion_confidence',
            'Emotion detection confidence scores',
            buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 0.95, 0.99]
        )
        
        # RAG metrics
        self.rag_retrievals = Counter(
            'rag_retrievals_total',
            'Number of RAG retrievals',
            ['backend']  # sqlite, chromadb
        )
        
        self.rag_latency = Histogram(
            'rag_retrieval_duration_seconds',
            'RAG retrieval latency',
            ['backend'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        )
        
        self.rag_results = Histogram(
            'rag_results_count',
            'Number of results returned by RAG',
            buckets=[1, 3, 5, 10, 20, 50]
        )
        
        # Memory metrics
        self.active_sessions = Gauge(
            'active_chat_sessions',
            'Number of active chat sessions'
        )
        
        self.memory_messages = Gauge(
            'memory_messages_total',
            'Total messages in memory',
            ['chat_id']
        )
        
        # Error metrics
        self.errors = Counter(
            'errors_total',
            'Total number of errors',
            ['type', 'endpoint']
        )
        
        # System info
        self.system_info = Info(
            'emotional_rag_info',
            'System information'
        )
        
        self.system_info.info({
            'version': '2.0.0',
            'model': settings.gemini_model,
            'embedding_model': settings.embedding_model,
            'chromadb_enabled': str(settings.enable_chromadb),
            'reranking_enabled': str(settings.enable_reranking),
            'redis_enabled': str(settings.enable_redis)
        })
        
        logger.info("Prometheus metrics collector initialized")
    
    def track_request(self, endpoint: str, status: str = "success") -> None:
        """Track a request completion.
        
        Args:
            endpoint: Endpoint name
            status: Request status (success/error)
        """
        if not self.enabled:
            return
        
        self.request_count.labels(endpoint=endpoint, status=status).inc()
    
    def track_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Track token usage.
        
        Args:
            prompt_tokens: Tokens in prompt
            completion_tokens: Tokens in completion
        """
        if not self.enabled:
            return
        
        self.tokens_used.labels(type='prompt').inc(prompt_tokens)
        self.tokens_used.labels(type='completion').inc(completion_tokens)
        self.tokens_used.labels(type='total').inc(prompt_tokens + completion_tokens)
    
    def track_context_tokens(
        self,
        system_tokens: int,
        rag_tokens: int,
        history_tokens: int
    ) -> None:
        """Track token distribution in context.
        
        Args:
            system_tokens: Tokens in system prompt
            rag_tokens: Tokens in RAG context
            history_tokens: Tokens in conversation history
        """
        if not self.enabled:
            return
        
        self.context_tokens.labels(component='system').observe(system_tokens)
        self.context_tokens.labels(component='rag').observe(rag_tokens)
        self.context_tokens.labels(component='history').observe(history_tokens)
    
    def track_emotion(self, emotion: str, confidence: Optional[float] = None) -> None:
        """Track emotion detection.
        
        Args:
            emotion: Detected emotion
            confidence: Confidence score (if available)
        """
        if not self.enabled:
            return
        
        self.emotion_count.labels(emotion=emotion).inc()
        
        if confidence is not None:
            self.emotion_confidence.observe(confidence)
    
    def track_rag_retrieval(
        self,
        backend: str,
        duration: float,
        result_count: int
    ) -> None:
        """Track RAG retrieval metrics.
        
        Args:
            backend: Storage backend (sqlite/chromadb)
            duration: Retrieval duration in seconds
            result_count: Number of results returned
        """
        if not self.enabled:
            return
        
        self.rag_retrievals.labels(backend=backend).inc()
        self.rag_latency.labels(backend=backend).observe(duration)
        self.rag_results.observe(result_count)
    
    def track_error(self, error_type: str, endpoint: str) -> None:
        """Track an error occurrence.
        
        Args:
            error_type: Type of error
            endpoint: Endpoint where error occurred
        """
        if not self.enabled:
            return
        
        self.errors.labels(type=error_type, endpoint=endpoint).inc()
    
    def update_active_sessions(self, count: int) -> None:
        """Update active session count.
        
        Args:
            count: Number of active sessions
        """
        if not self.enabled:
            return
        
        self.active_sessions.set(count)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format.
        
        Returns:
            Metrics data as bytes
        """
        if not self.enabled:
            return b"# Metrics not enabled\n"
        
        return generate_latest()
    
    def get_content_type(self) -> str:
        """Get Prometheus content type.
        
        Returns:
            Content type string
        """
        if not self.enabled:
            return "text/plain"
        
        return CONTENT_TYPE_LATEST


def track_latency(endpoint: str):
    """Decorator to track endpoint latency.
    
    Args:
        endpoint: Endpoint name
        
    Usage:
        @track_latency("chat_completion")
        async def chat(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                # Metrics will be tracked by the function itself
                # This is just for logging
                logger.debug(
                    f"{endpoint} completed",
                    extra={"duration": duration}
                )
        return wrapper
    return decorator
