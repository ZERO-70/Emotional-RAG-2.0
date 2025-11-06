"""Multi-tiered memory management system with SQLite persistence."""

import logging
import asyncio
import aiosqlite
from pathlib import Path
from collections import deque
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import numpy as np

from app.core.config import settings
from app.core.token_manager import TokenManager
from app.models.memory import (
    StoredMessage,
    PersonaData,
    ConversationSummary,
    EmotionalState
)
from app.services.rag_engine import RAGEngine
from app.services.emotion_tracker import EmotionTracker

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Multi-tiered memory manager with:
    - Working Memory (RAM): Last N messages
    - Short-Term Memory (SQLite): Full conversation history
    - Long-Term Memory (Embeddings): Semantic search
    """
    
    def __init__(
        self,
        rag_engine: RAGEngine,
        emotion_tracker: EmotionTracker,
        token_manager: TokenManager
    ):
        """
        Initialize memory manager.
        
        Args:
            rag_engine: RAG engine for embeddings
            emotion_tracker: Emotion detection service
            token_manager: Token counting service
        """
        self.rag_engine = rag_engine
        self.emotion_tracker = emotion_tracker
        self.token_manager = token_manager
        
        # Working memory: chat_id -> deque of recent messages
        self.working_memory: Dict[str, deque] = {}
        
        # Database connections pool (chat_id -> connection)
        self.db_connections: Dict[str, aiosqlite.Connection] = {}
        
        # Session metadata
        self.session_metadata: Dict[str, Dict] = {}
        
        logger.info("Memory manager initialized")
    
    async def get_db_connection(self, chat_id: str) -> aiosqlite.Connection:
        """
        Get or create database connection for chat session.
        
        Args:
            chat_id: Chat session identifier
            
        Returns:
            SQLite connection
        """
        if chat_id not in self.db_connections:
            db_path = Path(settings.db_path) / f"{chat_id}.db"
            conn = await aiosqlite.connect(str(db_path))
            conn.row_factory = aiosqlite.Row
            await self._init_database_schema(conn)
            self.db_connections[chat_id] = conn
            logger.info(f"Created database connection for chat: {chat_id}")
        
        return self.db_connections[chat_id]
    
    async def _init_database_schema(self, conn: aiosqlite.Connection):
        """Initialize database schema if not exists."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                emotional_state TEXT,
                importance_score REAL DEFAULT 0.5,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                chat_id TEXT PRIMARY KEY,
                persona_text TEXT NOT NULL,
                embedding BLOB,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                message_range TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
            ON messages(chat_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_importance 
            ON messages(importance_score DESC)
        """)
        
        await conn.commit()
    
    async def store_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        emotion: Optional[str] = None,
        importance: Optional[float] = None,
        generate_embedding: bool = True
    ) -> int:
        """
        Store message in both working memory and database.
        
        Args:
            chat_id: Chat session ID
            role: Message role (user/assistant/system)
            content: Message content
            emotion: Detected emotion
            importance: Importance score
            generate_embedding: Whether to generate embedding
            
        Returns:
            Message ID
        """
        # Add to working memory
        if chat_id not in self.working_memory:
            self.working_memory[chat_id] = deque(
                maxlen=settings.max_working_memory_size
            )
        
        message_dict = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.working_memory[chat_id].append(message_dict)
        
        # Generate embedding if requested
        embedding_bytes = None
        if generate_embedding and role in ['user', 'assistant']:
            try:
                embedding = self.rag_engine.encode(content)
                embedding_bytes = self.rag_engine.embedding_to_bytes(embedding)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        # Store in database
        conn = await self.get_db_connection(chat_id)
        cursor = await conn.execute("""
            INSERT INTO messages 
            (chat_id, role, content, embedding, emotional_state, importance_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            role,
            content,
            embedding_bytes,
            emotion,
            importance or 0.5
        ))
        
        await conn.commit()
        message_id = cursor.lastrowid
        
        logger.debug(
            f"Stored message {message_id}",
            extra={
                "chat_id": chat_id,
                "role": role,
                "content_length": len(content),
                "emotion": emotion,
                "importance": importance
            }
        )
        
        return message_id
    
    async def get_recent_messages(
        self,
        chat_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get recent messages from working memory or database.
        
        Args:
            chat_id: Chat session ID
            limit: Maximum messages to retrieve
            
        Returns:
            List of message dicts
        """
        # Try working memory first
        if chat_id in self.working_memory:
            messages = list(self.working_memory[chat_id])
            if len(messages) >= limit:
                return messages[-limit:]
        
        # Fall back to database
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT role, content, timestamp
            FROM messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (chat_id, limit)) as cursor:
            rows = await cursor.fetchall()
        
        messages = [
            {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"]
            }
            for row in reversed(rows)
        ]
        
        return messages
    
    async def get_message_count(self, chat_id: str) -> int:
        """Get total message count for session."""
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT COUNT(*) as count
            FROM messages
            WHERE chat_id = ?
        """, (chat_id,)) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0
    
    async def store_persona(
        self,
        chat_id: str,
        persona_text: str,
        generate_embeddings: bool = True
    ):
        """
        Store persona with optional chunked embeddings.
        
        Args:
            chat_id: Chat session ID
            persona_text: Persona/character card text
            generate_embeddings: Whether to generate embeddings
        """
        # Chunk persona for better retrieval
        chunks = self.rag_engine.chunk_text(persona_text, chunk_size=200)
        
        # Generate embeddings for chunks
        embedding_bytes = None
        if generate_embeddings:
            try:
                # Store combined embedding
                full_embedding = self.rag_engine.encode(persona_text)
                embedding_bytes = self.rag_engine.embedding_to_bytes(full_embedding)
                
                # Also store chunk embeddings in messages table as 'system' role
                chunk_embeddings = self.rag_engine.encode_batch(chunks)
                conn = await self.get_db_connection(chat_id)
                
                for chunk, chunk_emb in zip(chunks, chunk_embeddings):
                    emb_bytes = self.rag_engine.embedding_to_bytes(chunk_emb)
                    await conn.execute("""
                        INSERT INTO messages
                        (chat_id, role, content, embedding, importance_score)
                        VALUES (?, 'system', ?, ?, 1.0)
                    """, (chat_id, chunk, emb_bytes))
                
                await conn.commit()
                
            except Exception as e:
                logger.warning(f"Failed to generate persona embeddings: {e}")
        
        # Store main persona
        conn = await self.get_db_connection(chat_id)
        await conn.execute("""
            INSERT OR REPLACE INTO personas
            (chat_id, persona_text, embedding, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (chat_id, persona_text, embedding_bytes))
        
        await conn.commit()
        
        logger.info(
            f"Stored persona for chat: {chat_id}",
            extra={"chunks": len(chunks), "length": len(persona_text)}
        )
    
    async def get_persona(self, chat_id: str) -> Optional[str]:
        """Retrieve persona text."""
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT persona_text FROM personas WHERE chat_id = ?
        """, (chat_id,)) as cursor:
            row = await cursor.fetchone()
            return row["persona_text"] if row else None
    
    async def retrieve_semantic_context(
        self,
        chat_id: str,
        query: str,
        query_emotion: Optional[str] = None,
        top_k: int = 3,
        max_tokens: int = 1000
    ) -> str:
        """
        Retrieve semantically relevant context using RAG.
        
        Args:
            chat_id: Chat session ID
            query: Query text (usually current user message)
            query_emotion: Detected emotion for boosting
            top_k: Number of results to retrieve
            max_tokens: Maximum tokens in returned context
            
        Returns:
            Formatted context string
        """
        # Generate query embedding
        query_embedding = self.rag_engine.encode(query)
        
        # Retrieve messages with embeddings
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT content, role, emotional_state, importance_score, embedding
            FROM messages
            WHERE chat_id = ? AND embedding IS NOT NULL
            ORDER BY importance_score DESC
            LIMIT 50
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
        
        # Convert to candidate embeddings
        candidates = []
        for row in rows:
            if row["embedding"]:
                embedding = self.rag_engine.bytes_to_embedding(row["embedding"])
                metadata = {
                    "content": row["content"],
                    "source": "persona" if row["role"] == "system" else "message",
                    "emotion": row["emotional_state"],
                    "importance_score": row["importance_score"]
                }
                candidates.append((embedding, metadata))
        
        if not candidates:
            return ""
        
        # Search with emotional boosting
        results = self.rag_engine.search_embeddings(
            query_embedding=query_embedding,
            candidate_embeddings=candidates,
            top_k=top_k,
            emotional_boost=True,
            query_emotion=query_emotion
        )
        
        # Format for context
        formatted = self.rag_engine.format_results_for_context(
            results,
            max_tokens=max_tokens
        )
        
        logger.info(
            f"Retrieved {len(results)} RAG results",
            extra={
                "chat_id": chat_id,
                "results_count": len(results),
                "query_emotion": query_emotion
            }
        )
        
        return formatted
    
    async def should_summarize(self, chat_id: str) -> bool:
        """Check if conversation should be summarized."""
        message_count = await self.get_message_count(chat_id)
        
        # Get last summary point
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT MAX(id) as last_summary_id FROM summaries WHERE chat_id = ?
        """, (chat_id,)) as cursor:
            row = await cursor.fetchone()
            last_summary_id = row["last_summary_id"] if row else 0
        
        # Count messages since last summary
        async with conn.execute("""
            SELECT COUNT(*) as count FROM messages
            WHERE chat_id = ? AND id > ?
        """, (chat_id, last_summary_id or 0)) as cursor:
            row = await cursor.fetchone()
            messages_since_summary = row["count"] if row else 0
        
        should_summarize = messages_since_summary >= settings.summarize_after_messages
        
        logger.debug(
            f"Summarization check: {messages_since_summary}/{settings.summarize_after_messages}",
            extra={
                "chat_id": chat_id,
                "should_summarize": should_summarize
            }
        )
        
        return should_summarize
    
    async def create_summary(
        self,
        chat_id: str,
        gemini_client,
        message_range: Tuple[int, int] = None
    ) -> Optional[str]:
        """
        Create conversation summary using Gemini.
        
        Args:
            chat_id: Chat session ID
            gemini_client: Gemini client for summarization
            message_range: Optional (start_id, end_id) tuple
            
        Returns:
            Summary text
        """
        conn = await self.get_db_connection(chat_id)
        
        # Get messages to summarize
        if message_range:
            start_id, end_id = message_range
            query = """
                SELECT id, role, content, emotional_state
                FROM messages
                WHERE chat_id = ? AND id BETWEEN ? AND ?
                ORDER BY id
            """
            params = (chat_id, start_id, end_id)
        else:
            # Summarize oldest unsummarized messages
            async with conn.execute("""
                SELECT MAX(id) as last_id FROM summaries WHERE chat_id = ?
            """, (chat_id,)) as cursor:
                row = await cursor.fetchone()
                last_summary_id = row["last_id"] if row else 0
            
            query = """
                SELECT id, role, content, emotional_state
                FROM messages
                WHERE chat_id = ? AND id > ?
                ORDER BY id
                LIMIT ?
            """
            params = (chat_id, last_summary_id, settings.summarize_after_messages)
        
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        
        if not rows:
            return None
        
        # Build conversation text
        conversation_lines = []
        for row in rows:
            role_label = row["role"].upper()
            content = row["content"]
            emotion = f" [{row['emotional_state']}]" if row["emotional_state"] else ""
            conversation_lines.append(f"{role_label}{emotion}: {content}")
        
        conversation_text = "\n".join(conversation_lines)
        
        # Create summarization prompt
        summary_prompt = f"""Summarize the following conversation, preserving:
1. Key emotional moments and their context
2. Important facts, decisions, and revelations
3. Character development and relationship dynamics
4. Unresolved topics or ongoing threads

Keep the summary under 200 words and maintain narrative flow.

CONVERSATION:
{conversation_text}

SUMMARY:"""
        
        try:
            # Call Gemini for summary
            response = await gemini_client.chat_completion(
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.3,  # Lower temperature for factual summary
                max_tokens=300
            )
            
            summary_text = response.choices[0].message.content
            
            # Store summary
            message_range_str = f"{rows[0]['id']}-{rows[-1]['id']}"
            await conn.execute("""
                INSERT INTO summaries (chat_id, summary_text, message_range)
                VALUES (?, ?, ?)
            """, (chat_id, summary_text, message_range_str))
            
            await conn.commit()
            
            logger.info(
                f"Created summary for chat: {chat_id}",
                extra={
                    "message_range": message_range_str,
                    "summary_length": len(summary_text)
                }
            )
            
            return summary_text
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return None
    
    async def get_summaries(self, chat_id: str, limit: int = 3) -> List[str]:
        """Get recent conversation summaries."""
        conn = await self.get_db_connection(chat_id)
        async with conn.execute("""
            SELECT summary_text FROM summaries
            WHERE chat_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (chat_id, limit)) as cursor:
            rows = await cursor.fetchall()
        
        return [row["summary_text"] for row in rows]
    
    async def close_session(self, chat_id: str):
        """Close database connection for session."""
        if chat_id in self.db_connections:
            await self.db_connections[chat_id].close()
            del self.db_connections[chat_id]
            logger.info(f"Closed database connection for chat: {chat_id}")
    
    async def close_all(self):
        """Close all database connections."""
        for chat_id in list(self.db_connections.keys()):
            await self.close_session(chat_id)
    
    def check_db_connection(self) -> bool:
        """Health check for database connections."""
        try:
            return len(self.db_connections) >= 0  # Always true if no errors
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @property
    def active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.working_memory.keys())
