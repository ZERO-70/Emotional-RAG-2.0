"""Test suite for memory management."""

import pytest
import asyncio
from app.core.memory import MemoryManager
from app.services.rag_engine import RAGEngine
from app.services.emotion_tracker import EmotionTracker
from app.core.token_manager import TokenManager


@pytest.fixture
async def memory_manager():
    """Create memory manager instance for testing."""
    rag = RAGEngine()
    emotion = EmotionTracker()
    tokens = TokenManager()
    
    manager = MemoryManager(
        rag_engine=rag,
        emotion_tracker=emotion,
        token_manager=tokens
    )
    
    yield manager
    
    # Cleanup
    await manager.close_all()


@pytest.mark.asyncio
async def test_store_and_retrieve_message(memory_manager):
    """Test storing and retrieving messages."""
    chat_id = "test_chat_1"
    
    # Store a message
    msg_id = await memory_manager.store_message(
        chat_id=chat_id,
        role="user",
        content="Hello, how are you?",
        emotion="neutral",
        importance=0.5
    )
    
    assert msg_id > 0
    
    # Retrieve messages
    messages = await memory_manager.get_recent_messages(chat_id, limit=10)
    
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello, how are you?"
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_persona_storage(memory_manager):
    """Test persona storage and retrieval."""
    chat_id = "test_chat_2"
    persona_text = "You are a helpful AI assistant with a friendly personality."
    
    await memory_manager.store_persona(
        chat_id=chat_id,
        persona_text=persona_text
    )
    
    retrieved = await memory_manager.get_persona(chat_id)
    
    assert retrieved == persona_text


@pytest.mark.asyncio
async def test_semantic_retrieval(memory_manager):
    """Test semantic context retrieval."""
    chat_id = "test_chat_3"
    
    # Store some messages with embeddings
    await memory_manager.store_message(
        chat_id=chat_id,
        role="user",
        content="I love pizza",
        emotion="joy",
        importance=0.8,
        generate_embedding=True
    )
    
    await memory_manager.store_message(
        chat_id=chat_id,
        role="user",
        content="I'm feeling sad today",
        emotion="sadness",
        importance=0.9,
        generate_embedding=True
    )
    
    # Retrieve context
    context = await memory_manager.retrieve_semantic_context(
        chat_id=chat_id,
        query="What food do I like?",
        top_k=1
    )
    
    assert "pizza" in context.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
