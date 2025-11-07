#!/usr/bin/env python3
"""Debug script to check memory storage and retrieval."""

import asyncio
import sqlite3
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings


async def check_memory_storage(chat_id: str = None):
    """Check what's stored in the database."""
    
    print("=" * 60)
    print("Memory Storage Diagnostic")
    print("=" * 60)
    
    # Find all session databases
    sessions_path = Path(settings.db_path)
    if not sessions_path.exists():
        print(f"\n❌ Sessions directory not found: {sessions_path}")
        return
    
    db_files = list(sessions_path.glob("*.db"))
    
    if not db_files:
        print(f"\n⚠️  No session databases found in {sessions_path}")
        return
    
    print(f"\n📁 Found {len(db_files)} session database(s):")
    for db_file in db_files:
        print(f"   - {db_file.name}")
    
    # If specific chat_id provided, check that one
    if chat_id:
        db_files = [sessions_path / f"{chat_id}.db"]
        if not db_files[0].exists():
            print(f"\n❌ Database for chat_id '{chat_id}' not found")
            return
    
    # Analyze each database
    for db_file in db_files:
        print(f"\n" + "=" * 60)
        print(f"Database: {db_file.name}")
        print("=" * 60)
        
        try:
            conn = sqlite3.connect(str(db_file))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check messages table
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            message_count = cursor.fetchone()["count"]
            print(f"\n📨 Total Messages: {message_count}")
            
            if message_count > 0:
                # Check embeddings
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embeddings,
                        SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as without_embeddings
                    FROM messages
                """)
                emb_stats = cursor.fetchone()
                print(f"   - With embeddings: {emb_stats['with_embeddings']}")
                print(f"   - Without embeddings: {emb_stats['without_embeddings']}")
                
                # Show recent messages
                print(f"\n📜 Recent Messages (last 10):")
                cursor.execute("""
                    SELECT id, role, content, emotional_state, importance_score, 
                           CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding,
                           timestamp
                    FROM messages
                    ORDER BY id DESC
                    LIMIT 10
                """)
                
                messages = cursor.fetchall()
                for msg in reversed(messages):
                    content_preview = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
                    print(f"\n   [{msg['id']}] {msg['role'].upper()}: {content_preview}")
                    print(f"       Emotion: {msg['emotional_state'] or 'None'}, "
                          f"Importance: {msg['importance_score']:.2f}, "
                          f"Embedding: {msg['has_embedding']}, "
                          f"Time: {msg['timestamp']}")
            
            # Check persona
            cursor.execute("SELECT COUNT(*) as count FROM personas")
            persona_count = cursor.fetchone()["count"]
            print(f"\n👤 Personas: {persona_count}")
            
            if persona_count > 0:
                cursor.execute("""
                    SELECT persona_text, 
                           CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding,
                           updated_at
                    FROM personas
                """)
                persona = cursor.fetchone()
                persona_preview = persona["persona_text"][:100] + "..." if len(persona["persona_text"]) > 100 else persona["persona_text"]
                print(f"   Persona: {persona_preview}")
                print(f"   Embedding: {persona['has_embedding']}")
                print(f"   Updated: {persona['updated_at']}")
            
            # Check summaries
            cursor.execute("SELECT COUNT(*) as count FROM summaries")
            summary_count = cursor.fetchone()["count"]
            print(f"\n📋 Summaries: {summary_count}")
            
            conn.close()
            
        except Exception as e:
            print(f"\n❌ Error reading database: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Diagnostic Complete")
    print("=" * 60)


async def test_rag_retrieval(chat_id: str, query: str):
    """Test RAG retrieval for a specific query."""
    from app.core.memory import MemoryManager
    from app.services.rag_engine import RAGEngine
    from app.services.emotion_tracker import EmotionTracker
    from app.core.token_manager import TokenManager
    
    print("\n" + "=" * 60)
    print("RAG Retrieval Test")
    print("=" * 60)
    
    print(f"\nChat ID: {chat_id}")
    print(f"Query: {query}")
    
    # Initialize services
    rag_engine = RAGEngine()
    emotion_tracker = EmotionTracker()
    token_manager = TokenManager()
    memory_manager = MemoryManager(rag_engine, token_manager)
    
    # Detect emotion
    emotion_state = emotion_tracker.detect_emotion(query)
    print(f"\nDetected Emotion: {emotion_state.emotion} (confidence: {emotion_state.confidence:.2f})")
    
    # Retrieve context
    print("\nRetrieving semantic context...")
    context = await memory_manager.retrieve_semantic_context(
        chat_id=chat_id,
        query=query,
        query_emotion=emotion_state.emotion,
        top_k=3,
        max_tokens=1000
    )
    
    print("\n📚 Retrieved Context:")
    print("-" * 60)
    if context:
        print(context)
    else:
        print("(No context retrieved)")
    print("-" * 60)
    
    # Also get recent messages
    print("\n💬 Recent Messages:")
    recent = await memory_manager.get_recent_messages(chat_id, limit=5)
    for msg in recent:
        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        content_preview = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        print(f"{role_emoji} {msg['role']}: {content_preview}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug memory storage and retrieval")
    parser.add_argument("--chat-id", help="Specific chat ID to analyze")
    parser.add_argument("--test-query", help="Test RAG retrieval with this query")
    
    args = parser.parse_args()
    
    # Run storage check
    asyncio.run(check_memory_storage(args.chat_id))
    
    # If test query provided, run retrieval test
    if args.test_query and args.chat_id:
        asyncio.run(test_rag_retrieval(args.chat_id, args.test_query))
    elif args.test_query:
        print("\n⚠️  --test-query requires --chat-id to be specified")
