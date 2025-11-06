# GitHub Copilot Instructions

## Project Overview
**Emotional RAG Backend** - Production FastAPI system solving LLM persona forgetting via proactive memory management, semantic retrieval (RAG), and emotional context tracking. Integrates with SillyTavern using OpenAI-compatible API + Google Gemini.

## Architecture Principles

### Three-Tier Memory System (Core Pattern)
```python
# app/core/memory.py - THE central component
MemoryManager orchestrates:
  1. Working Memory (RAM) → deque[maxlen=20] per chat_id
  2. Short-Term (SQLite) → Full history + embeddings as BLOB
  3. Long-Term (Vectors) → Semantic search via sentence-transformers
```

**Critical**: Always use `chat_id` from `request.user` field (SillyTavern sends session ID here). Never use default chat IDs in production code.

### Dependency Injection via Global Singletons
```python
# app/main.py lifespan creates globals:
gemini_client, rag_engine, emotion_tracker, token_manager, memory_manager

# Routes import from app.main (NOT dependency injection):
from app.main import gemini_client, memory_manager  # ✓ Correct
# NOT: async def chat(manager: MemoryManager = Depends())  # ✗ Wrong pattern
```

## Critical Workflows

### Chat Request Flow (8 Steps - See app/routes/chat.py)
```python
1. Extract chat_id from request.user (SillyTavern convention)
2. Detect emotion → emotion_tracker.detect_emotion(user_message)
3. Check/create persona → memory_manager.get_persona() or store from system msg
4. RAG retrieval → memory_manager.retrieve_semantic_context(emotion_boost=True)
5. Build context with token budget → token_manager.allocate_token_budget()
6. Call Gemini → gemini_client.chat_completion(stream=True/False)
7. Store with metadata → memory_manager.store_message(emotion, importance)
8. Check summarization → if should_summarize(): asyncio.create_task(summarize)
```

### Token Budget Allocation (20/25/35/20 Split)
```python
# app/core/config.py properties:
system_token_budget    = 20% (persona, NEVER truncate)
rag_token_budget       = 25% (retrieved memories)
history_token_budget   = 35% (recent conversation)
response_token_budget  = 20% (LLM output space)

# Usage in context building:
budget = token_manager.allocate_token_budget()
persona_truncated = token_manager.truncate_to_token_limit(
    persona, max_tokens=budget['system'], preserve_start=True
)
```

### Async Database Pattern (aiosqlite)
```python
# ALWAYS use async with aiosqlite:
conn = await memory_manager.get_db_connection(chat_id)
async with conn.execute("SELECT ...") as cursor:
    rows = await cursor.fetchall()

# Store embeddings as BLOB:
embedding_bytes = rag_engine.embedding_to_bytes(np_array)
await conn.execute("INSERT ... VALUES (?, ?)", (content, embedding_bytes))
```

## Project-Specific Conventions

### Structured Logging (JSON)
```python
logger.info(
    "Context built",  # Message
    extra={           # Structured data
        "chat_id": chat_id,
        "total_tokens": 1234,
        "emotion": "joy"
    }
)
# Outputs JSON via pythonjsonlogger to logs/app.log
```

### Error Handling in Routes
```python
# Pattern: try/except with HTTPException
try:
    response = await gemini_client.chat_completion(...)
except google_exceptions.ResourceExhausted:
    logger.warning("Rate limit hit")
    raise  # tenacity retry handles
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=str(e))
```

### Pydantic Models & Settings
```python
# app/models/chat.py - OpenAI compatibility
ChatCompletionRequest.user → SillyTavern sends chat_id here
Message.role → Literal["system", "user", "assistant"]

# app/core/config.py - All settings from .env
settings.gemini_api_key  # Required
settings.port = 8001     # NOT 8000 (SillyTavern's port)
```

## Integration Points

### SillyTavern Configuration
```yaml
# CRITICAL: Port confusion
SillyTavern UI:    http://localhost:8000 (their server)
This Backend:      http://localhost:8001 (our API)
API URL setting:   http://localhost:8001/v1  # Must include /v1

# request.user field contains chat_id for session isolation
```

### Gemini API Client (app/services/gemini_client.py)
```python
# Message format conversion (OpenAI → Gemini):
def _convert_messages_to_prompt(messages):
    # Gemini uses concatenated text, not message arrays
    # System → "INSTRUCTIONS:\n{content}"
    # User → "USER: {content}"
    # Final: "ASSISTANT:" to prime response

# Retry with tenacity on specific exceptions:
@retry(retry=retry_if_exception_type((
    google_exceptions.ResourceExhausted,  # Rate limit
    google_exceptions.ServiceUnavailable
)))
```

### RAG Engine (app/services/rag_engine.py)
```python
# sentence-transformers: all-MiniLM-L6-v2 (384-dim, fast)
embedding = rag_engine.encode(text)  # → np.ndarray

# Emotional boosting pattern:
if message_emotion == query_emotion and emotion != 'neutral':
    similarity_score *= (1 + importance_score * 0.3)

# Chunk personas for better retrieval:
chunks = rag_engine.chunk_text(persona, chunk_size=200, overlap=50)
```

## Development Commands

### Setup & Run
```bash
python3 setup.py           # Automated setup
./run.sh                   # Start server (port 8001)
python3 verify.py          # Verify installation
```

### Testing
```bash
pytest tests/ -v                    # All tests
pytest tests/test_memory.py -v     # Specific suite
python examples/test_usage.py       # Manual integration test
curl http://localhost:8001/health   # Health check
```

### Debugging
```bash
# Logs: logs/app.log (JSON format)
tail -f logs/app.log | jq .

# Database inspection:
sqlite3 data/sessions/{chat_id}.db
sqlite> SELECT COUNT(*) FROM messages;
sqlite> SELECT * FROM personas;

# Check active sessions:
curl http://localhost:8001/health | jq .memory_sessions
```

## Common Pitfalls

### ❌ Don't Do This
```python
# Wrong: Default chat IDs lose session isolation
chat_id = "default"  

# Wrong: Sync SQLite with async FastAPI
conn = sqlite3.connect(...)  # Use aiosqlite!

# Wrong: Truncate persona (violates core principle)
if len(persona) > 1000: persona = persona[:1000]

# Wrong: OpenAI format sent directly to Gemini
response = gemini.chat(messages=openai_messages)
```

### ✓ Do This Instead
```python
# Extract from request.user
chat_id = request.user or f"anon_{uuid.uuid4().hex[:8]}"

# Async all the way
conn = await aiosqlite.connect(...)

# Truncate to token budget, preserve start
persona = token_manager.truncate_to_token_limit(
    persona, max_tokens=budget['system'], preserve_start=True
)

# Convert format first
prompt = gemini_client._convert_messages_to_prompt(messages)
```

## File Organization Patterns

```
app/
├── main.py              # FastAPI app + lifespan + globals
├── core/                # Business logic
│   ├── memory.py       # ⭐ Central orchestrator (581 lines)
│   ├── token_manager.py # Budget allocation
│   └── config.py       # Pydantic settings
├── services/           # External integrations
│   ├── gemini_client.py  # LLM API wrapper
│   ├── rag_engine.py     # Embeddings + search
│   └── emotion_tracker.py # Detection + scoring
├── routes/             # API endpoints
│   ├── chat.py        # /v1/chat/completions (433 lines)
│   └── health.py      # /health monitoring
└── models/            # Pydantic schemas
    ├── chat.py        # OpenAI-compatible
    └── memory.py      # Domain models

data/sessions/{chat_id}.db  # Per-session SQLite
```

## Future Architecture (Phase 2+)

The current implementation is Phase 1 MVP. Planned evolution paths:

### Vector Database Migration (ChromaDB)
```python
# CURRENT: SQLite BLOB storage + in-memory numpy search
# FUTURE: Dedicated vector database with advanced indexing

from chromadb import Client
chroma_client = Client()
collection = chroma_client.create_collection("memories")

# Benefits:
- Persistent vector indices (no rebuild on startup)
- HNSW/IVF indexing for 100k+ embeddings
- Multi-modal embeddings (text + images)
- Distributed deployment support
```

### Reranking Pipeline (Cross-Encoders)
```python
# CURRENT: Single-stage retrieval (bi-encoder cosine similarity)
# FUTURE: Two-stage retrieve + rerank

from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Workflow:
1. Retrieve top 50 candidates via bi-encoder (fast)
2. Rerank top 50 → 10 via cross-encoder (accurate)
3. Score boost: 0.85 → 0.92 relevance

# Integration point: memory_manager.retrieve_semantic_context()
```

### Advanced Emotion Detection
```python
# CURRENT: Keyword-based emotion detection (emotion_tracker.py)
# FUTURE: Transformer-based emotion classification

from transformers import pipeline
emotion_classifier = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base"
)

# Upgrades:
- 7 emotions → 28 fine-grained emotions
- Confidence scores (not binary)
- Multi-label (joy + excitement simultaneously)
- Sarcasm/irony detection

# Migration: Keep keyword fallback for speed-critical paths
```

### Distributed Memory (Redis)
```python
# CURRENT: In-process working memory (deque)
# FUTURE: Shared memory across multiple backend instances

import redis.asyncio as redis
redis_client = await redis.from_url("redis://localhost")

# Architecture:
- Working memory → Redis sorted sets (TTL: 30min)
- Enable horizontal scaling (multiple Uvicorn workers)
- Session affinity not required
- Pub/sub for memory invalidation

# Compatibility: Keep SQLite for persistence layer
```

### PostgreSQL Migration
```python
# CURRENT: SQLite per-session (data/sessions/{chat_id}.db)
# FUTURE: Centralized PostgreSQL with connection pooling

from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://...")

# Schema changes:
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(255) INDEX,  -- Partition key
    embedding vector(384),       -- pgvector extension
    emotion VARCHAR(50),
    ...
)

# Benefits:
- ACID transactions across sessions
- Full-text search (tsvector)
- Streaming replication
- Point-in-time recovery
```

### Production Deployment Enhancements

**Docker Multi-Stage Build**
```dockerfile
# Dockerfile (future)
FROM python:3.11-slim AS builder
RUN pip install --target=/deps -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages
# Image size: 450MB → 280MB
```

**Observability Stack**
```python
# Prometheus metrics (future addition)
from prometheus_client import Counter, Histogram

request_count = Counter('chat_requests_total', 'Total chat requests')
response_time = Histogram('chat_response_seconds', 'Response latency')

# Grafana dashboards:
- Token usage over time
- Emotion distribution
- RAG retrieval accuracy
- Memory growth rate per session
```

**Health Check Enhancements**
```python
# CURRENT: Basic /health endpoint
# FUTURE: Detailed subsystem checks

{
    "status": "healthy",
    "checks": {
        "gemini_api": "ok",        # Ping test
        "database": "ok",           # Connection pool status
        "vector_index": "ok",       # Index health
        "memory_usage": "warning"   # RAM > 80%
    },
    "metrics": {
        "active_sessions": 42,
        "avg_response_time_ms": 1234
    }
}
```

### Migration Strategy

When implementing Phase 2 features:

1. **Feature Flags**: Use `.env` to toggle new features without breaking existing deployments
   ```python
   ENABLE_CHROMADB = os.getenv("ENABLE_CHROMADB", "false") == "true"
   ```

2. **Backward Compatibility**: Support both old and new storage simultaneously during migration
   ```python
   if ENABLE_CHROMADB:
       embeddings = await chroma_search(...)
   else:
       embeddings = await sqlite_search(...)  # Fallback
   ```

3. **Data Migration Script**: Provide `migrate_to_phase2.py` for existing users
   ```bash
   python migrate_to_phase2.py --source sqlite --target postgres
   ```

4. **Performance Testing**: Benchmark before/after to validate improvements
   - Target: <500ms p95 response time with 10k memories
   - Current: ~300ms with 1k memories (SQLite)

### Breaking Changes to Anticipate

- **ChromaDB**: Requires separate service (Docker Compose)
- **PostgreSQL**: Migration script needed for existing SQLite users
- **Redis**: Additional infrastructure dependency
- **Cross-Encoder**: 10x slower than bi-encoder (use selectively)

### Non-Goals (Explicitly Out of Scope)

- **On-premise LLM**: Stick with Gemini API (cost/performance tradeoff)
- **Real-time training**: Pre-trained models only, no fine-tuning
- **Multi-user auth**: SillyTavern handles this, we trust chat_id
- **Web UI**: API-only backend, SillyTavern is the frontend

---

## When Making Changes

**Adding new emotion types**: Update `emotion_tracker.emotion_keywords` dict + `emotion_weights`

**Changing token budgets**: Modify percentages in `.env`, NOT hardcoded in code

**New RAG retrieval strategies**: Extend `rag_engine.search_embeddings()` with new scoring

**Summarization triggers**: Adjust `settings.summarize_after_messages` (default: 20)

**Model switching**: Update `GEMINI_MODEL` in `.env` (gemini-2.0-flash-exp, gemini-1.5-pro, etc.)

---

**Priority**: Memory persistence > Speed. Never lose chat history. All writes are committed immediately.
