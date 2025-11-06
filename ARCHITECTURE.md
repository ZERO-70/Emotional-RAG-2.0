# Architecture Documentation

## System Overview

The Emotional RAG Backend is a production-ready FastAPI application that solves persona forgetting in LLM conversations through proactive memory management, semantic retrieval, and emotional context tracking.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        SillyTavern                          │
│                  (Frontend / User Interface)                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         │ OpenAI-compatible API
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              API Routes (app/routes/)                │   │
│  │  • /v1/chat/completions  (chat.py)                  │   │
│  │  • /v1/models            (chat.py)                  │   │
│  │  • /health               (health.py)                │   │
│  └────────────┬──────────────────────────┬──────────────┘   │
│               │                          │                  │
│               ↓                          ↓                  │
│  ┌────────────────────────┐  ┌────────────────────────┐    │
│  │   Core Services        │  │   Memory Manager       │    │
│  │  (app/services/)       │  │  (app/core/memory.py)  │    │
│  │                        │  │                        │    │
│  │  • GeminiClient        │←→│  Working Memory (RAM)  │    │
│  │  • RAGEngine           │  │  Short-Term (SQLite)   │    │
│  │  • EmotionTracker      │  │  Long-Term (Vectors)   │    │
│  │  • TokenManager        │  │                        │    │
│  └────────────────────────┘  └────────────────────────┘    │
└────────────────┬────────────────────────┬───────────────────┘
                 │                        │
                 ↓                        ↓
┌─────────────────────────┐  ┌──────────────────────────┐
│    Google Gemini API    │  │   Data Persistence       │
│   (LLM Generation)      │  │                          │
│  • gemini-1.5-pro       │  │  • SQLite databases      │
│  • Streaming support    │  │    (per session)         │
│  • Retry logic          │  │  • Embedding cache       │
└─────────────────────────┘  │  • Conversation history  │
                              └──────────────────────────┘
```

---

## Component Details

### 1. API Layer (`app/routes/`)

**chat.py** - Main chat endpoint
- OpenAI-compatible `/v1/chat/completions`
- Streaming and non-streaming modes
- Session management via `user` field
- Context building orchestration

**health.py** - Health monitoring
- System status checks
- Database connectivity
- Gemini API status
- Active session count

### 2. Core Services (`app/services/`)

#### GeminiClient
```python
# Responsibilities:
- Async API calls to Google Gemini
- Retry logic with exponential backoff
- Rate limiting (5 concurrent requests)
- Streaming response handling
- Token usage tracking
```

#### RAGEngine
```python
# Responsibilities:
- Text embedding with sentence-transformers
- Semantic similarity search
- Persona chunking and indexing
- Context formatting
- Embedding serialization
```

#### EmotionTracker
```python
# Responsibilities:
- Keyword-based emotion detection
- Importance scoring (0-1 scale)
- Emotional context prompts
- Relevance boosting for matching emotions
```

#### TokenManager
```python
# Responsibilities:
- Token counting (tiktoken)
- Budget allocation across components
- Message truncation
- Context size optimization
```

### 3. Memory Manager (`app/core/memory.py`)

The heart of the system - implements three-tier memory:

#### Working Memory (RAM)
```python
# Structure: Dict[chat_id, deque(maxlen=20)]
{
  "chat_123": deque([
    {"role": "user", "content": "...", "timestamp": "..."},
    {"role": "assistant", "content": "...", "timestamp": "..."},
    # ... last 20 messages
  ])
}
```

#### Short-Term Memory (SQLite)
```sql
-- Per-session database: data/sessions/{chat_id}.db

-- Full conversation history
messages (
  id, chat_id, role, content,
  embedding, emotional_state,
  importance_score, timestamp
)

-- Character definitions
personas (
  chat_id, persona_text,
  embedding, updated_at
)

-- Compressed history
summaries (
  id, chat_id, summary_text,
  message_range, created_at
)
```

#### Long-Term Memory (Embeddings)
- Embeddings stored in SQLite BLOB format
- Semantic search via cosine similarity
- Emotional boosting for relevance
- Persona chunk indexing

---

## Request Flow

### Standard Chat Completion

```
1. Request arrives at /v1/chat/completions
   ├─ Extract chat_id from request.user
   └─ Parse user message

2. Emotion Detection
   ├─ Analyze user message for emotion
   ├─ Calculate importance score
   └─ Store emotional state

3. Memory Retrieval
   ├─ Check if persona exists
   │  └─ If not, extract and index
   ├─ Retrieve semantic context (RAG)
   │  ├─ Generate query embedding
   │  ├─ Search message embeddings
   │  └─ Boost emotionally similar
   └─ Get recent conversation history

4. Context Building
   ├─ Allocate token budget
   │  ├─ System/Persona: 20%
   │  ├─ RAG Context: 25%
   │  ├─ History: 35%
   │  └─ Response: 20%
   ├─ Build system prompt
   ├─ Format RAG results
   ├─ Fit history to budget
   └─ Assemble final context

5. LLM Generation
   ├─ Call Gemini API
   │  ├─ With retry logic
   │  └─ Rate limiting
   └─ Stream or return full response

6. Storage
   ├─ Store user message
   │  ├─ Generate embedding
   │  ├─ Save emotion metadata
   │  └─ Calculate importance
   ├─ Store assistant message
   └─ Update working memory

7. Post-Processing
   ├─ Check if summarization needed
   │  └─ If yes, trigger background task
   └─ Return response to client
```

---

## Memory Management Strategy

### Token Budget Allocation

For a 4096 token context window:

```
┌─────────────────────────────────────────┐
│  System/Persona (20%) = 800 tokens      │ Always included
├─────────────────────────────────────────┤
│  RAG Context (25%) = 1000 tokens        │ Semantic retrieval
├─────────────────────────────────────────┤
│  History (35%) = 1400 tokens            │ Recent conversation
├─────────────────────────────────────────┤
│  Response Buffer (20%) = 800 tokens     │ Model output
└─────────────────────────────────────────┘
```

### Summarization Trigger

```python
# Automatic summarization when:
if messages_since_last_summary >= 20:
    summary = await gemini.summarize(old_messages)
    store_summary(summary)
    # Old messages compressed to ~200 word summary
    # Preserves: emotional moments, decisions, context
```

### Context Building Algorithm

```python
def build_context(chat_id, user_message):
    """
    Smart context assembly with priority:
    1. ALWAYS include full persona (never truncate)
    2. Retrieve top-3 semantically relevant chunks
    3. Add recent 10 messages (or fit to budget)
    4. Include summaries if history truncated
    5. Add current user message
    """
    context = []
    
    # Priority 1: Persona (critical)
    persona = get_persona(chat_id)
    context.append({"role": "system", "content": persona})
    
    # Priority 2: RAG context (semantic relevance)
    rag = retrieve_semantic(user_message, top_k=3)
    if rag:
        context.append({"role": "system", "content": rag})
    
    # Priority 3: History (recent conversation)
    history = get_recent_messages(chat_id, limit=20)
    fitted_history = fit_to_budget(history, budget=1400)
    
    if len(fitted_history) < len(history):
        # History truncated, add summary
        summary = get_latest_summary(chat_id)
        context.append({"role": "system", "content": summary})
    
    context.extend(fitted_history)
    
    # Priority 4: Current message
    context.append({"role": "user", "content": user_message})
    
    return context
```

---

## Semantic Retrieval (RAG)

### Embedding Generation

```python
# Model: all-MiniLM-L6-v2 (sentence-transformers)
# Dimension: 384
# Speed: ~1000 sentences/sec on CPU

text = "I love pizza"
embedding = model.encode(text)
# → numpy array [0.123, -0.456, 0.789, ...]
```

### Similarity Search

```python
# Cosine similarity between query and candidates
query_emb = encode("What food do I like?")

scores = []
for msg in messages_with_embeddings:
    similarity = cosine_similarity(query_emb, msg.embedding)
    
    # Emotional boosting
    if msg.emotion == query_emotion:
        similarity *= (1 + msg.importance_score * 0.3)
    
    scores.append((similarity, msg))

# Return top-k
return sorted(scores, reverse=True)[:3]
```

### Persona Chunking

```python
# Large personas are chunked for better retrieval
persona = "You are Aria, a 25-year-old AI researcher..."  # 2000 chars

chunks = chunk_text(persona, chunk_size=200, overlap=50)
# → [
#     "You are Aria, a 25-year-old AI researcher...",
#     "...researcher who loves science fiction and...",
#     "...fiction and philosophy. You have a warm...",
#     # etc.
# ]

# Each chunk gets its own embedding
embeddings = encode_batch(chunks)

# Stored in database for semantic search
```

---

## Emotional Context System

### Emotion Detection

```python
# Keywords-based (Phase 1)
emotions = {
    'joy': ['happy', 'excited', 'love', '😊'],
    'sadness': ['sad', 'hurt', 'cry', '😢'],
    'anger': ['angry', 'furious', '😠'],
    'fear': ['scared', 'worried', '😰'],
    # etc.
}

# Count matches
scores = {emotion: count_keywords(text, kws) 
          for emotion, kws in emotions.items()}

# Dominant emotion
emotion = max(scores, key=scores.get)
confidence = min(scores[emotion] / 3.0, 1.0)
```

### Importance Scoring

```python
def calculate_importance(text, emotion, confidence):
    score = 0.5  # baseline
    
    # Factor 1: Emotional intensity
    if emotion != 'neutral':
        score += confidence * emotion_weight * 0.3
    
    # Factor 2: Length (detail indicator)
    if len(text) > 200:
        score += 0.15
    
    # Factor 3: Questions (engagement)
    score += min(text.count('?') * 0.1, 0.15)
    
    # Factor 4: Exclamations (emphasis)
    score += min(text.count('!') * 0.05, 0.1)
    
    # Factor 5: Personal pronouns (investment)
    pronouns = ['i ', 'me ', 'my ']
    score += min(count_pronouns(text) * 0.05, 0.1)
    
    return min(score, 1.0)
```

### Dynamic System Prompts

```python
# Emotional context added to system prompt
if emotion == 'sadness' and confidence > 0.6:
    prompt += """
    ## Emotional Context
    User is feeling sad (confidence: 85%)
    Respond with empathy, validation, and gentle support.
    
    **Relevant past emotional moments:**
    - "I was really hurt when..." (3 days ago)
    - "Feeling down about..." (1 week ago)
    """
```

---

## Performance Characteristics

### Latency Breakdown

```
Total Response Time: ~1.5-3.0 seconds

├─ Emotion Detection:     10-20ms
├─ RAG Retrieval:         50-100ms
│  ├─ Embedding generation: 20ms
│  ├─ Similarity search:    30ms
│  └─ Formatting:           10ms
├─ Context Building:      20-50ms
├─ Gemini API Call:       1000-2500ms
│  ├─ Network latency:    100-200ms
│  └─ Model generation:   900-2300ms
└─ Storage:               50-100ms
   ├─ Embedding:          30ms
   └─ Database write:     20ms
```

### Resource Usage

```
Memory:
├─ Base application:     ~200MB
├─ Embedding model:      ~400MB
├─ Working memory:       ~50MB per 100 sessions
└─ Total (typical):      ~650MB

Disk:
├─ Application code:     ~5MB
├─ Dependencies:         ~800MB
├─ Embedding model:      ~80MB
├─ Per-session DB:       ~100KB-5MB
└─ Total (typical):      ~1GB

CPU:
├─ Idle:                 <1%
├─ During request:       20-40% (embedding)
└─ Concurrent requests:  Scales linearly
```

### Scalability

```
Single Instance:
├─ Concurrent requests:  5 (Gemini rate limit)
├─ Sessions:            1000+ (limited by RAM)
├─ Messages/day:        10,000+
└─ Disk growth:         ~10MB/1000 messages

Multi-Instance (Phase 2):
├─ Add Redis for shared working memory
├─ Load balancer for API requests
├─ Shared PostgreSQL for persistence
└─ Handles: 100+ concurrent users
```

---

## Security Considerations

### Current Implementation

```
✅ Environment-based secrets (.env)
✅ CORS middleware (configurable origins)
✅ Input validation (Pydantic models)
✅ SQL injection protection (parameterized queries)
✅ Rate limiting (per Gemini API)

⚠️  No authentication (local use assumed)
⚠️  HTTP only (no TLS)
⚠️  Open CORS (development mode)
```

### Production Recommendations

```python
# 1. Add authentication
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.post("/v1/chat/completions")
async def chat(request: Request, token: str = Depends(security)):
    verify_token(token)  # Implement token validation
    # ...

# 2. Enable HTTPS
uvicorn.run(
    app,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)

# 3. Restrict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-sillytavern.com"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Authorization"]
)

# 4. Rate limiting per user
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/v1/chat/completions")
@limiter.limit("60/minute")
async def chat(...):
    # ...
```

---

## Monitoring & Observability

### Structured Logging

```json
{
  "timestamp": "2025-11-04T10:30:45.123Z",
  "level": "INFO",
  "name": "app.routes.chat",
  "message": "Chat completion successful",
  "chat_id": "user_123",
  "input_tokens": 1234,
  "output_tokens": 456,
  "total_tokens": 1690,
  "latency_seconds": 2.34
}
```

### Health Metrics

```python
GET /health

{
  "status": "healthy",
  "gemini_api": true,
  "database": true,
  "memory_sessions": 12,
  "timestamp": "2025-11-04T10:30:45Z"
}
```

### Usage Tracking

```python
# Per-session cost tracking
session_stats = {
    "total_input_tokens": 45000,
    "total_output_tokens": 12000,
    "estimated_cost": 0.12  # USD
}
```

---

## Deployment Options

### Option 1: Local Development
```bash
uvicorn app.main:app --reload --host localhost --port 8000
```

### Option 2: Production Server
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Option 3: Docker (Phase 2)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

### Option 4: Cloud (AWS/GCP/Azure)
```yaml
# Example: AWS Elastic Beanstalk
environment:
  - GEMINI_API_KEY: ${GEMINI_KEY}
  - DB_PATH: /data/sessions
scaling:
  min_instances: 1
  max_instances: 5
```

---

## Future Enhancements (Phase 2)

### Advanced RAG
- ChromaDB for persistent vector storage
- Cross-encoder reranking
- Hybrid search (semantic + keyword)
- Metadata filtering

### Emotion Detection
- Transformer-based models (BERT)
- Multi-label classification
- Sentiment intensity scoring

### Distributed System
- Redis for shared memory
- PostgreSQL for persistence
- Message queue (RabbitMQ)
- Horizontal scaling

### Monitoring
- Prometheus metrics
- Grafana dashboards
- OpenTelemetry tracing
- Alert system

---

## Troubleshooting Guide

### Common Issues

**High Memory Usage**
```bash
# Solution: Reduce working memory size
# In .env:
MAX_WORKING_MEMORY_SIZE=10
```

**Slow Responses**
```bash
# Solution: Reduce RAG top-k
RAG_TOP_K=1

# Or use faster model
GEMINI_MODEL=gemini-1.5-flash
```

**Database Locked**
```bash
# Solution: Close stale connections
sqlite3 data/sessions/chat.db "PRAGMA journal_mode=WAL;"
```

**Embedding Errors**
```bash
# Solution: Clear model cache
rm -rf ~/.cache/torch/sentence_transformers/
```

---

## Performance Tuning

### For Speed
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Fastest
RAG_TOP_K=1
MAX_WORKING_MEMORY_SIZE=10
SUMMARIZE_AFTER_MESSAGES=30
```

### For Quality
```env
EMBEDDING_MODEL=all-mpnet-base-v2  # Better quality
RAG_TOP_K=5
MAX_WORKING_MEMORY_SIZE=30
SUMMARIZE_AFTER_MESSAGES=15
```

### For Cost Optimization
```env
GEMINI_MODEL=gemini-1.5-flash  # Cheaper
SYSTEM_TOKEN_PERCENT=15
RAG_TOKEN_PERCENT=20
```

---

**This architecture is designed to be production-ready, scalable, and easy to extend!**
