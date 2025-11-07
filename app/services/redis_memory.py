"""Redis-based distributed working memory.

Phase 2 enhancement providing:
- Shared memory across multiple backend instances
- Automatic TTL-based expiration
- Pub/sub for memory invalidation
- Enables horizontal scaling
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisMemoryStore:
    """Redis-based distributed working memory with TTL.
    
    Benefits over in-process deque:
    - Shared across multiple Uvicorn workers
    - Persistent across restarts (with AOF/RDB)
    - Automatic expiration via TTL
    - Pub/sub for cache invalidation
    """
    
    def __init__(self):
        """Initialize Redis connection pool."""
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis not installed. Install with: pip install 'redis[hiredis]>=7.0.0'"
            )
        
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.ttl = settings.redis_ttl
        
        logger.info(
            "Redis memory store initializing",
            extra={"url": settings.redis_url, "ttl": self.ttl}
        )
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self.client = redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True,
                encoding="utf-8"
            )
            
            # Test connection
            await self.client.ping()
            
            # Initialize pub/sub
            self.pubsub = self.client.pubsub()
            
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            raise
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()
        logger.info("Redis connection closed")
    
    def _working_memory_key(self, chat_id: str) -> str:
        """Generate Redis key for working memory."""
        return f"working_memory:{chat_id}"
    
    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add message to working memory sorted set.
        
        Uses timestamp as score for chronological ordering.
        
        Args:
            chat_id: Chat session identifier
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata (emotion, importance, etc.)
        """
        key = self._working_memory_key(chat_id)
        timestamp = datetime.utcnow().timestamp()
        
        # Serialize message with metadata
        message_data = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            **(metadata or {})
        }
        
        try:
            # Add to sorted set with timestamp as score
            await self.client.zadd(
                key,
                {json.dumps(message_data): timestamp}
            )
            
            # Set expiration on the key
            await self.client.expire(key, self.ttl)
            
            # Trim to max size (keep most recent messages)
            await self.client.zremrangebyrank(
                key,
                0,
                -(settings.max_working_memory_size + 1)
            )
            
            logger.debug(
                "Message added to Redis working memory",
                extra={"chat_id": chat_id, "role": role}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to add message to Redis: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            raise
    
    async def get_messages(
        self,
        chat_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages from working memory.
        
        Args:
            chat_id: Chat session identifier
            limit: Maximum number of messages (default: all)
            
        Returns:
            List of message dictionaries
        """
        key = self._working_memory_key(chat_id)
        limit = limit or settings.max_working_memory_size
        
        try:
            # Get most recent messages (highest scores)
            messages_json = await self.client.zrange(
                key,
                -limit,
                -1,
                withscores=False
            )
            
            # Deserialize messages
            messages = [json.loads(msg) for msg in messages_json]
            
            logger.debug(
                "Retrieved messages from Redis",
                extra={"chat_id": chat_id, "count": len(messages)}
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                f"Failed to get messages from Redis: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            return []
    
    async def clear_memory(self, chat_id: str) -> None:
        """Clear working memory for a chat session.
        
        Args:
            chat_id: Chat session identifier
        """
        key = self._working_memory_key(chat_id)
        
        try:
            await self.client.delete(key)
            
            # Publish invalidation event
            await self.client.publish(
                "memory_invalidation",
                json.dumps({"chat_id": chat_id, "action": "clear"})
            )
            
            logger.info(
                "Cleared Redis working memory",
                extra={"chat_id": chat_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to clear Redis memory: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            raise
    
    async def get_memory_size(self, chat_id: str) -> int:
        """Get number of messages in working memory.
        
        Args:
            chat_id: Chat session identifier
            
        Returns:
            Message count
        """
        key = self._working_memory_key(chat_id)
        
        try:
            count = await self.client.zcard(key)
            return count
        except Exception as e:
            logger.error(
                f"Failed to get memory size: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            return 0
    
    async def subscribe_to_invalidation(self) -> None:
        """Subscribe to memory invalidation events."""
        if not self.pubsub:
            logger.warning("Pub/sub not initialized")
            return
        
        try:
            await self.pubsub.subscribe("memory_invalidation")
            logger.info("Subscribed to memory invalidation channel")
        except Exception as e:
            logger.error(f"Failed to subscribe to invalidation: {e}", exc_info=True)
    
    async def handle_invalidation_messages(self) -> None:
        """Listen for and handle invalidation messages."""
        if not self.pubsub:
            return
        
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    logger.info(
                        "Received invalidation event",
                        extra=data
                    )
                    # Additional handling can be added here
        except Exception as e:
            logger.error(f"Error handling invalidation: {e}", exc_info=True)
