# Architecture Documentation# Architecture Documentation



## System Overview## System Overview



The Emotional RAG Backend is a production-ready FastAPI application that solves persona forgetting in LLM conversations through:The Emotional RAG Backend is a production-ready FastAPI application that solves persona forgetting in LLM conversations through proactive memory management, semantic retrieval, and emotional context tracking.

- **Proactive memory management** (3-tier system)

- **Semantic retrieval** (RAG with embeddings)---

- **Emotional context tracking** (importance scoring)

## Architecture Diagram

---

```

## High-Level Architecture┌─────────────────────────────────────────────────────────────┐

│                        SillyTavern                          │

```│                  (Frontend / User Interface)                │

┌──────────────────────────────────────────────────────────────────┐└────────────────────────┬────────────────────────────────────┘

│                        SillyTavern                               │                         │ HTTP/REST

│                   (Frontend / User Interface)                    │                         │ OpenAI-compatible API

└──────────────────────────┬───────────────────────────────────────┘                         ↓

                           │ HTTP/REST (OpenAI-compatible API)┌─────────────────────────────────────────────────────────────┐

                           ↓│                     FastAPI Application                     │

┌──────────────────────────────────────────────────────────────────┐│  ┌──────────────────────────────────────────────────────┐   │

│                     FastAPI Application                          ││  │              API Routes (app/routes/)                │   │

│  ┌────────────────────────────────────────────────────────────┐  ││  │  • /v1/chat/completions  (chat.py)                  │   │

│  │            API Routes (app/routes/)                        │  ││  │  • /v1/models            (chat.py)                  │   │

│  │  /v1/chat/completions  |  /v1/models  |  /health          │  ││  │  • /health               (health.py)                │   │

│  └────────────┬────────────────────────┬──────────────────────┘  ││  └────────────┬──────────────────────────┬──────────────┘   │

│               │                        │                         ││               │                          │                  │

│  ┌────────────▼─────────┐   ┌──────────▼─────────────────────┐  ││               ↓                          ↓                  │

│  │   Core Services      │   │   Memory Manager               │  ││  ┌────────────────────────┐  ┌────────────────────────┐    │

│  │  (app/services/)     │◄─►│   (app/core/memory.py)         │  ││  │   Core Services        │  │   Memory Manager       │    │

│  │                      │   │                                │  ││  │  (app/services/)       │  │  (app/core/memory.py)  │    │

│  │  • GeminiClient      │   │  ┌──────────────────────────┐  │  ││  │                        │  │                        │    │

│  │  • RAGEngine         │   │  │  Working Memory (RAM)   │  │  ││  │  • GeminiClient        │←→│  Working Memory (RAM)  │    │

│  │  • EmotionTracker    │   │  │  deque[20 messages]     │  │  ││  │  • RAGEngine           │  │  Short-Term (SQLite)   │    │

│  │  • TokenManager      │   │  └──────────────────────────┘  │  ││  │  • EmotionTracker      │  │  Long-Term (Vectors)   │    │

│  │  • ChromaDBStore*    │   │  ┌──────────────────────────┐  │  ││  │  • TokenManager        │  │                        │    │

│  │  • Reranker*         │   │  │  Short-Term (SQLite)    │  │  ││  └────────────────────────┘  └────────────────────────┘    │

│  │  • Transformer       │   │  │  Full history + metadata│  │  │└────────────────┬────────────────────────┬───────────────────┘

│  │    Emotions*         │   │  └──────────────────────────┘  │  │                 │                        │

│  │  • RedisMemory*      │   │  ┌──────────────────────────┐  │  │                 ↓                        ↓

│  │  • Metrics*          │   │  │  Long-Term (Embeddings) │  │  │┌─────────────────────────┐  ┌──────────────────────────┐

│  └──────────────────────┘   │  │  Semantic search (RAG)  │  │  ││    Google Gemini API    │  │   Data Persistence       │

│                              │  └──────────────────────────┘  │  ││   (LLM Generation)      │  │                          │

│  * Phase 2 components        └────────────────────────────────┘  ││  • gemini-1.5-pro       │  │  • SQLite databases      │

└──────────┬──────────────────────────────┬────────────────────────┘│  • Streaming support    │  │    (per session)         │

           │                              ││  • Retry logic          │  │  • Embedding cache       │

           ↓                              ↓└─────────────────────────┘  │  • Conversation history  │

┌────────────────────────┐   ┌────────────────────────────────────┐                              └──────────────────────────┘

│  Google Gemini API     │   │    Data Persistence                │```

│  (LLM Generation)      │   │                                    │

│  • gemini-2.0-flash    │   │  • SQLite per session              │---

│  • Streaming support   │   │    (data/sessions/*.db)            │

│  • Retry logic         │   │  • ChromaDB vectors* (optional)    │## Component Details

│  • Rate limiting       │   │  • Redis cache* (optional)         │

└────────────────────────┘   │  • PostgreSQL* (optional)          │### 1. API Layer (`app/routes/`)

                              └────────────────────────────────────┘

```**chat.py** - Main chat endpoint

- OpenAI-compatible `/v1/chat/completions`

---- Streaming and non-streaming modes

- Session management via `user` field

## Component Details- Context building orchestration



### 1. API Layer (`app/routes/`)**health.py** - Health monitoring

- System status checks

#### chat.py - Main Chat Endpoint- Database connectivity

- Gemini API status

**Responsibilities**:- Active session count

- OpenAI-compatible `/v1/chat/completions`

- Streaming and non-streaming responses### 2. Core Services (`app/services/`)

- Session management via `user` field (SillyTavern sends chat_id here)

- Context building orchestration#### GeminiClient

```python

**Request Flow**:# Responsibilities:

```python- Async API calls to Google Gemini

1. Extract chat_id from request.user- Retry logic with exponential backoff

2. Detect emotion from user message- Rate limiting (5 concurrent requests)

3. Check/create persona from system message- Streaming response handling

4. Retrieve semantic context (RAG)- Token usage tracking

5. Build context with token budget```

6. Call Gemini API

7. Store messages with embeddings#### RAGEngine

8. Check summarization trigger```python

9. Return response# Responsibilities:

```- Text embedding with sentence-transformers

- Semantic similarity search

**Key Features**:- Persona chunking and indexing

- Uses SillyTavern's conversation context (from `request.messages`)- Context formatting

- Supplements with RAG-retrieved long-term memories- Embedding serialization

- Stores all messages for future retrieval```



#### health.py - Monitoring#### EmotionTracker

```python

**Endpoints**:# Responsibilities:

- `/health` - System status, DB connectivity, active sessions- Keyword-based emotion detection

- `/metrics` - Prometheus metrics (if `ENABLE_METRICS=true`)- Importance scoring (0-1 scale)

- Emotional context prompts

### 2. Core Services- Relevance boosting for matching emotions

```

#### GeminiClient (`app/services/gemini_client.py`)

#### TokenManager

**Purpose**: Async wrapper for Google Gemini API```python

# Responsibilities:

**Features**:- Token counting (tiktoken)

```python- Budget allocation across components

• Async API calls with asyncio.to_thread()- Message truncation

• Retry logic with exponential backoff (tenacity)- Context size optimization

• Rate limiting (max 5 concurrent requests)```

• Streaming response handling

• Token usage tracking### 3. Memory Manager (`app/core/memory.py`)

• Error handling for quota/rate limits

```The heart of the system - implements three-tier memory:



**Message Format Conversion**:#### Working Memory (RAM)

```python```python

# OpenAI format → Gemini format# Structure: Dict[chat_id, deque(maxlen=20)]

[{role: "system", content: "..."},{

 {role: "user", content: "..."}]  "chat_123": deque([

    ↓    {"role": "user", "content": "...", "timestamp": "..."},

"INSTRUCTIONS:\n...\n\nUSER: ...\n\nASSISTANT:"    {"role": "assistant", "content": "...", "timestamp": "..."},

```    # ... last 20 messages

  ])

#### RAGEngine (`app/services/rag_engine.py`)}

```

**Purpose**: Semantic similarity search using sentence-transformers

#### Short-Term Memory (SQLite)

**Model**: `all-MiniLM-L6-v2` (384-dimensional embeddings)```sql

-- Per-session database: data/sessions/{chat_id}.db

**Capabilities**:

```python-- Full conversation history

• encode(text) → np.ndarray[384]messages (

• search_embeddings(query, candidates, top_k)  id, chat_id, role, content,

• Emotional boosting (increases relevance for matching emotions)  embedding, emotional_state,

• Persona chunking (200 chars, 50 overlap)  importance_score, timestamp

• Embedding serialization (numpy ↔ bytes))

```

-- Character definitions

**Search Algorithm**:personas (

```python  chat_id, persona_text,

1. Compute query embedding  embedding, updated_at

2. Calculate cosine similarity with all candidates)

3. Apply emotional boost: similarity *= (1 + importance * 0.3)

4. Sort by similarity descending-- Compressed history

5. Return top_k resultssummaries (

```  id, chat_id, summary_text,

  message_range, created_at

#### EmotionTracker (`app/services/emotion_tracker.py`))

```

**Purpose**: Keyword-based emotion detection + importance scoring

#### Long-Term Memory (Embeddings)

**Emotion Categories**:- Embeddings stored in SQLite BLOB format

- Joy, Sadness, Anger, Fear, Surprise, Disgust, Neutral- Semantic search via cosine similarity

- Emotional boosting for relevance

**Importance Scoring** (0.0 - 1.0):- Persona chunk indexing

```python

score = base_emotion_weight + length_factor---



# Factors:## Request Flow

• Emotion weight (joy: 0.7, anger: 0.8, etc.)

• Message length (longer = more important)### Standard Chat Completion

• Normalized to 0.0 - 1.0 range

``````

1. Request arrives at /v1/chat/completions

**Phase 2 Upgrade** (`transformer_emotions.py`):   ├─ Extract chat_id from request.user

- Uses `j-hartmann/emotion-english-distilroberta-base`   └─ Parse user message

- 7 fine-grained emotions with confidence scores

- Multi-label support2. Emotion Detection

- 66% accuracy on test set   ├─ Analyze user message for emotion

   ├─ Calculate importance score

#### TokenManager (`app/core/token_manager.py`)   └─ Store emotional state



**Purpose**: Token budget allocation and context building3. Memory Retrieval

   ├─ Check if persona exists

**Budget Allocation** (128k context window):   │  └─ If not, extract and index

```   ├─ Retrieve semantic context (RAG)

System/Persona:     20% → ~25,600 tokens (persona NEVER truncated at start)   │  ├─ Generate query embedding

RAG Context:        25% → ~32,000 tokens (retrieved memories)   │  ├─ Search message embeddings

History:            35% → ~44,800 tokens (recent conversation)   │  └─ Boost emotionally similar

Response Buffer:    20% → ~25,600 tokens (LLM output space)   └─ Get recent conversation history

```

4. Context Building

**Key Methods**:   ├─ Allocate token budget

```python   │  ├─ System/Persona: 20%

• allocate_token_budget() → dict[str, int]   │  ├─ RAG Context: 25%

• truncate_to_token_limit(text, max_tokens, preserve_start=True)   │  ├─ History: 35%

• fit_messages_to_budget(messages, budget, keep_recent=10)   │  └─ Response: 20%

• count_tokens(text) → int (using tiktoken cl100k_base)   ├─ Build system prompt

```   ├─ Format RAG results

   ├─ Fit history to budget

### 3. Memory Management   └─ Assemble final context



#### MemoryManager (`app/core/memory.py`)5. LLM Generation

   ├─ Call Gemini API

**Purpose**: Orchestrates 3-tier memory system   │  ├─ With retry logic

   │  └─ Rate limiting

**Architecture**:   └─ Stream or return full response

```python

┌─────────────────────────────────────┐6. Storage

│  Working Memory (RAM)               │   ├─ Store user message

│  deque[maxlen=20] per chat_id       │   │  ├─ Generate embedding

│  • Instant access                   │   │  ├─ Save emotion metadata

│  • Last 10-20 messages              │   │  └─ Calculate importance

└─────────────────────────────────────┘   ├─ Store assistant message

           ↓ (writes)   └─ Update working memory

┌─────────────────────────────────────┐

│  Short-Term Memory (SQLite)         │7. Post-Processing

│  data/sessions/{chat_id}.db         │   ├─ Check if summarization needed

│  • Full conversation history        │   │  └─ If yes, trigger background task

│  • Embeddings as BLOB               │   └─ Return response to client

│  • Emotion + importance metadata    │```

└─────────────────────────────────────┘

           ↓ (indexed)---

┌─────────────────────────────────────┐

│  Long-Term Memory (Vectors)         │## Memory Management Strategy

│  SQLite BLOB or ChromaDB*           │

│  • Semantic similarity search       │### Token Budget Allocation

│  • Emotional boosting               │

│  • Cross-encoder reranking*         │For a 4096 token context window:

└─────────────────────────────────────┘

``````

┌─────────────────────────────────────────┐

**Database Schema**:│  System/Persona (20%) = 800 tokens      │ Always included

```sql├─────────────────────────────────────────┤

-- messages table│  RAG Context (25%) = 1000 tokens        │ Semantic retrieval

CREATE TABLE messages (├─────────────────────────────────────────┤

    id INTEGER PRIMARY KEY,│  History (35%) = 1400 tokens            │ Recent conversation

    chat_id TEXT NOT NULL,├─────────────────────────────────────────┤

    role TEXT NOT NULL,│  Response Buffer (20%) = 800 tokens     │ Model output

    content TEXT NOT NULL,└─────────────────────────────────────────┘

    embedding BLOB,              -- numpy array as bytes```

    emotional_state TEXT,         -- detected emotion

    importance_score REAL,        -- 0.0 - 1.0### Summarization Trigger

    timestamp DATETIME

);```python

# Automatic summarization when:

-- personas tableif messages_since_last_summary >= 20:

CREATE TABLE personas (    summary = await gemini.summarize(old_messages)

    chat_id TEXT PRIMARY KEY,    store_summary(summary)

    persona_text TEXT NOT NULL,    # Old messages compressed to ~200 word summary

    embedding BLOB,    # Preserves: emotional moments, decisions, context

    updated_at DATETIME```

);

### Context Building Algorithm

-- summaries table

CREATE TABLE summaries (```python

    id INTEGER PRIMARY KEY,def build_context(chat_id, user_message):

    chat_id TEXT NOT NULL,    """

    summary_text TEXT NOT NULL,    Smart context assembly with priority:

    message_range TEXT,          -- "1-20"    1. ALWAYS include full persona (never truncate)

    created_at DATETIME    2. Retrieve top-3 semantically relevant chunks

);    3. Add recent 10 messages (or fit to budget)

```    4. Include summaries if history truncated

    5. Add current user message

**Key Methods**:    """

```python    context = []

• store_message(chat_id, role, content, emotion, importance)    

• get_recent_messages(chat_id, limit=20)    # Priority 1: Persona (critical)

• retrieve_semantic_context(chat_id, query, emotion, top_k=3)    persona = get_persona(chat_id)

• store_persona(chat_id, persona_text, generate_embeddings=True)    context.append({"role": "system", "content": persona})

• should_summarize(chat_id) → bool (checks message count)    

```    # Priority 2: RAG context (semantic relevance)

    rag = retrieve_semantic(user_message, top_k=3)

---    if rag:

        context.append({"role": "system", "content": rag})

## Phase 2 Enhancements    

    # Priority 3: History (recent conversation)

### ChromaDBVectorStore (`app/services/chromadb_store.py`)    history = get_recent_messages(chat_id, limit=20)

    fitted_history = fit_to_budget(history, budget=1400)

**Replaces**: SQLite BLOB storage for embeddings    

    if len(fitted_history) < len(history):

**Benefits**:        # History truncated, add summary

- Persistent HNSW indices (faster startup, no rebuild)        summary = get_latest_summary(chat_id)

- Native vector operations        context.append({"role": "system", "content": summary})

- Scalable to 100k+ embeddings    

- Metadata filtering    context.extend(fitted_history)

    

**Configuration**:    # Priority 4: Current message

```python    context.append({"role": "user", "content": user_message})

# Persistent mode (default)    

CHROMADB_PATH=./data/chromadb    return context

```

# Client-server mode

CHROMADB_HOST=localhost---

CHROMADB_PORT=8000

```## Semantic Retrieval (RAG)



### Reranker (`app/services/reranker.py`)### Embedding Generation



**Purpose**: Two-stage retrieval for better accuracy```python

# Model: all-MiniLM-L6-v2 (sentence-transformers)

**Model**: `cross-encoder/ms-marco-MiniLM-L6-v2` (MRR@10: 74.30)# Dimension: 384

# Speed: ~1000 sentences/sec on CPU

**Workflow**:

```pythontext = "I love pizza"

1. Bi-encoder retrieves top 50 candidates (fast, approximate)embedding = model.encode(text)

2. Cross-encoder reranks → top 10 (slow, accurate)# → numpy array [0.123, -0.456, 0.789, ...]

3. Result: Better relevance with minimal latency```

```

### Similarity Search

**Performance**:

- Throughput: ~1800 queries/second```python

- Latency: <1ms per query-document pair# Cosine similarity between query and candidates

query_emb = encode("What food do I like?")

### TransformerEmotionDetector (`app/services/transformer_emotions.py`)

scores = []

**Purpose**: Fine-grained emotion detection with confidencefor msg in messages_with_embeddings:

    similarity = cosine_similarity(query_emb, msg.embedding)

**Model**: `j-hartmann/emotion-english-distilroberta-base`    

    # Emotional boosting

**Features**:    if msg.emotion == query_emotion:

```python        similarity *= (1 + msg.importance_score * 0.3)

• 7 emotions: anger, disgust, fear, joy, neutral, sadness, surprise    

• Confidence scores (0.0 - 1.0)    scores.append((similarity, msg))

• Multi-label support (multiple emotions per message)

• Fallback to keyword-based if model fails# Return top-k

```return sorted(scores, reverse=True)[:3]

```

**Accuracy**: 66% on test set

### Persona Chunking

### RedisMemoryStore (`app/services/redis_memory.py`)

```python

**Purpose**: Distributed working memory across multiple workers# Large personas are chunked for better retrieval

persona = "You are Aria, a 25-year-old AI researcher..."  # 2000 chars

**Benefits**:

- Shared memory (no per-worker duplication)chunks = chunk_text(persona, chunk_size=200, overlap=50)

- TTL-based expiration (30 min default)# → [

- Pub/sub for cache invalidation#     "You are Aria, a 25-year-old AI researcher...",

- Enables horizontal scaling#     "...researcher who loves science fiction and...",

#     "...fiction and philosophy. You have a warm...",

**Data Structure**:#     # etc.

```python# ]

# Sorted set per chat_id

redis_key = f"memory:{chat_id}"# Each chunk gets its own embedding

ZADD memory:chat_123 timestamp1 message1_jsonembeddings = encode_batch(chunks)

ZADD memory:chat_123 timestamp2 message2_json

# Stored in database for semantic search

# TTL```

EXPIRE memory:chat_123 1800  # 30 minutes

```---



### MetricsCollector (`app/services/metrics.py`)## Emotional Context System



**Purpose**: Prometheus observability### Emotion Detection



**Metrics**:```python

```python# Keywords-based (Phase 1)

# Countersemotions = {

chat_requests_total    'joy': ['happy', 'excited', 'love', '😊'],

chat_errors_total    'sadness': ['sad', 'hurt', 'cry', '😢'],

    'anger': ['angry', 'furious', '😠'],

# Histograms    'fear': ['scared', 'worried', '😰'],

chat_response_time_seconds    # etc.

token_usage_total}



# Gauges# Count matches

active_sessionsscores = {emotion: count_keywords(text, kws) 

memory_usage_bytes          for emotion, kws in emotions.items()}



# Summaries# Dominant emotion

rag_retrieval_latencyemotion = max(scores, key=scores.get)

emotion_detection_latencyconfidence = min(scores[emotion] / 3.0, 1.0)

``````



**Access**: `http://localhost:8001/metrics`### Importance Scoring



---```python

def calculate_importance(text, emotion, confidence):

## Request Processing Flow    score = 0.5  # baseline

    

### Chat Completion Request    # Factor 1: Emotional intensity

    if emotion != 'neutral':

```        score += confidence * emotion_weight * 0.3

1. SillyTavern Request Arrives    

   ↓    # Factor 2: Length (detail indicator)

   POST /v1/chat/completions    if len(text) > 200:

   {        score += 0.15

     "messages": [...full conversation...],    

     "user": "chat_session_123",  ← chat_id    # Factor 3: Questions (engagement)

     "model": "gemini-2.0-flash-exp"    score += min(text.count('?') * 0.1, 0.15)

   }    

    # Factor 4: Exclamations (emphasis)

2. Extract Context    score += min(text.count('!') * 0.05, 0.1)

   ↓    

   chat_id = request.user || "default"    # Factor 5: Personal pronouns (investment)

   user_message = last message with role="user"    pronouns = ['i ', 'me ', 'my ']

   history = all previous user/assistant messages    score += min(count_pronouns(text) * 0.05, 0.1)

    

3. Emotion Detection    return min(score, 1.0)

   ↓```

   emotion_state = emotion_tracker.detect_emotion(user_message)

   # Returns: {emotion: "joy", confidence: 0.85, importance: 0.7}### Dynamic System Prompts



4. Persona Retrieval/Storage```python

   ↓# Emotional context added to system prompt

   persona = await memory_manager.get_persona(chat_id)if emotion == 'sadness' and confidence > 0.6:

   if not persona:    prompt += """

       extract from system message in request.messages    ## Emotional Context

       store with embeddings    User is feeling sad (confidence: 85%)

    Respond with empathy, validation, and gentle support.

5. RAG Retrieval (Semantic Search)    

   ↓    **Relevant past emotional moments:**

   query_embedding = rag_engine.encode(user_message)    - "I was really hurt when..." (3 days ago)

       - "Feeling down about..." (1 week ago)

   # Search database    """

   relevant_messages = await memory_manager.retrieve_semantic_context(```

       chat_id, 

       user_message, ---

       emotion=emotion_state.emotion,

       top_k=3## Performance Characteristics

   )

   ### Latency Breakdown

   # Phase 2: Rerank with cross-encoder

   if ENABLE_RERANKING:```

       relevant_messages = reranker.rerank(user_message, relevant_messages)Total Response Time: ~1.5-3.0 seconds



6. Context Building├─ Emotion Detection:     10-20ms

   ↓├─ RAG Retrieval:         50-100ms

   budget = token_manager.allocate_token_budget()│  ├─ Embedding generation: 20ms

   │  ├─ Similarity search:    30ms

   context_messages = [│  └─ Formatting:           10ms

       {role: "system", content: persona},           # 20% budget├─ Context Building:      20-50ms

       {role: "system", content: rag_context},       # 25% budget├─ Gemini API Call:       1000-2500ms

       ...history_messages,                          # 35% budget│  ├─ Network latency:    100-200ms

       {role: "user", content: user_message}│  └─ Model generation:   900-2300ms

   ]└─ Storage:               50-100ms

   ├─ Embedding:          30ms

7. Gemini API Call   └─ Database write:     20ms

   ↓```

   response = await gemini_client.chat_completion(

       messages=context_messages,### Resource Usage

       temperature=0.9,

       max_tokens=800```

   )Memory:

├─ Base application:     ~200MB

8. Store Messages├─ Embedding model:      ~400MB

   ↓├─ Working memory:       ~50MB per 100 sessions

   await memory_manager.store_message(└─ Total (typical):      ~650MB

       chat_id, "user", user_message, 

       emotion=emotion_state.emotion,Disk:

       importance=emotion_state.importance,├─ Application code:     ~5MB

       generate_embedding=True├─ Dependencies:         ~800MB

   )├─ Embedding model:      ~80MB

   ├─ Per-session DB:       ~100KB-5MB

   await memory_manager.store_message(└─ Total (typical):      ~1GB

       chat_id, "assistant", response.content,

       generate_embedding=TrueCPU:

   )├─ Idle:                 <1%

├─ During request:       20-40% (embedding)

9. Check Summarization└─ Concurrent requests:  Scales linearly

   ↓```

   if await memory_manager.should_summarize(chat_id):

       asyncio.create_task(### Scalability

           memory_manager.summarize_conversation(chat_id)

       )```

Single Instance:

10. Return Response├─ Concurrent requests:  5 (Gemini rate limit)

    ↓├─ Sessions:            1000+ (limited by RAM)

    return ChatCompletionResponse(...)├─ Messages/day:        10,000+

```└─ Disk growth:         ~10MB/1000 messages



---Multi-Instance (Phase 2):

├─ Add Redis for shared working memory

## Data Flow Diagrams├─ Load balancer for API requests

├─ Shared PostgreSQL for persistence

### Memory Storage Flow└─ Handles: 100+ concurrent users

```

```

User Message---

    ↓

┌─────────────────────┐## Security Considerations

│ 1. Add to Working   │

│    Memory (RAM)     │### Current Implementation

│    deque.append()   │

└──────────┬──────────┘```

           ↓✅ Environment-based secrets (.env)

┌─────────────────────┐✅ CORS middleware (configurable origins)

│ 2. Generate         │✅ Input validation (Pydantic models)

│    Embedding        │✅ SQL injection protection (parameterized queries)

│    RAG.encode()     │✅ Rate limiting (per Gemini API)

└──────────┬──────────┘

           ↓⚠️  No authentication (local use assumed)

┌─────────────────────┐⚠️  HTTP only (no TLS)

│ 3. Store in SQLite  │⚠️  Open CORS (development mode)

│    with metadata    │```

│    (emotion,        │

│     importance)     │### Production Recommendations

└──────────┬──────────┘

           ↓```python

┌─────────────────────┐# 1. Add authentication

│ 4. Optional: Store  │from fastapi import Depends, HTTPException

│    in ChromaDB*     │from fastapi.security import HTTPBearer

│    (Phase 2)        │

└─────────────────────┘security = HTTPBearer()

```

@app.post("/v1/chat/completions")

### RAG Retrieval Flowasync def chat(request: Request, token: str = Depends(security)):

    verify_token(token)  # Implement token validation

```    # ...

Query: "What is my name?"

    ↓# 2. Enable HTTPS

┌──────────────────────────┐uvicorn.run(

│ 1. Detect Emotion        │    app,

│    emotion = "neutral"   │    ssl_keyfile="key.pem",

│    confidence = 0.5      │    ssl_certfile="cert.pem"

└────────────┬─────────────┘)

             ↓

┌──────────────────────────┐# 3. Restrict CORS

│ 2. Generate Embedding    │app.add_middleware(

│    query_emb = [0.2,     │    CORSMiddleware,

│    0.5, -0.1, ...]       │    allow_origins=["https://your-sillytavern.com"],

└────────────┬─────────────┘    allow_credentials=True,

             ↓    allow_methods=["POST", "GET"],

┌──────────────────────────┐    allow_headers=["Content-Type", "Authorization"]

│ 3. Retrieve Candidates   │)

│    (Bi-encoder)          │

│    Top 50 by cosine      │# 4. Rate limiting per user

│    similarity            │from slowapi import Limiter

└────────────┬─────────────┘limiter = Limiter(key_func=get_remote_address)

             ↓

┌──────────────────────────┐@app.post("/v1/chat/completions")

│ 4. Apply Emotional Boost │@limiter.limit("60/minute")

│    if msg.emotion ==     │async def chat(...):

│       query.emotion:     │    # ...

│      score *= (1 + imp)  │```

└────────────┬─────────────┘

             ↓---

┌──────────────────────────┐

│ 5. Rerank* (Phase 2)     │## Monitoring & Observability

│    Cross-encoder:        │

│    50 → 10 best          │### Structured Logging

└────────────┬─────────────┘

             ↓```json

┌──────────────────────────┐{

│ 6. Format for Context    │  "timestamp": "2025-11-04T10:30:45.123Z",

│    "Retrieved Context:   │  "level": "INFO",

│     - My name is Alice   │  "name": "app.routes.chat",

│     - I love coding"     │  "message": "Chat completion successful",

└──────────────────────────┘  "chat_id": "user_123",

```  "input_tokens": 1234,

  "output_tokens": 456,

---  "total_tokens": 1690,

  "latency_seconds": 2.34

## Configuration}

```

### Environment Variables

### Health Metrics

See `.env.example` for full configuration.

```python

**Core Settings**:GET /health

```env

GEMINI_API_KEY=...{

GEMINI_MODEL=gemini-2.0-flash-exp  "status": "healthy",

PORT=8001  "gemini_api": true,

```  "database": true,

  "memory_sessions": 12,

**Memory**:  "timestamp": "2025-11-04T10:30:45Z"

```env}

MAX_WORKING_MEMORY_SIZE=20```

SUMMARIZE_AFTER_MESSAGES=20

DB_PATH=./data/sessions### Usage Tracking

```

```python

**RAG**:# Per-session cost tracking

```envsession_stats = {

EMBEDDING_MODEL=all-MiniLM-L6-v2    "total_input_tokens": 45000,

RAG_TOP_K=3    "total_output_tokens": 12000,

```    "estimated_cost": 0.12  # USD

}

**Token Budget**:```

```env

SYSTEM_TOKEN_PERCENT=20---

RAG_TOKEN_PERCENT=25

HISTORY_TOKEN_PERCENT=35## Deployment Options

RESPONSE_TOKEN_PERCENT=20

```### Option 1: Local Development

```bash

**Phase 2 Features**:uvicorn app.main:app --reload --host localhost --port 8000

```env```

ENABLE_CHROMADB=true

ENABLE_RERANKING=true### Option 2: Production Server

ENABLE_TRANSFORMER_EMOTIONS=true```bash

ENABLE_REDIS=false          # Needs Redis servergunicorn app.main:app \

ENABLE_POSTGRESQL=false     # Needs PostgreSQL server  --workers 4 \

ENABLE_METRICS=true  --worker-class uvicorn.workers.UvicornWorker \

```  --bind 0.0.0.0:8000

```

---

### Option 3: Docker (Phase 2)

## Deployment Architecture```dockerfile

FROM python:3.11-slim

### Single Server (Default)WORKDIR /app

COPY requirements.txt .

```RUN pip install -r requirements.txt

┌─────────────────────────────┐COPY . .

│  Server (localhost:8001)    │CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]

│  ┌───────────────────────┐  │```

│  │  FastAPI + Uvicorn    │  │

│  │  (single worker)      │  │### Option 4: Cloud (AWS/GCP/Azure)

│  └───────────────────────┘  │```yaml

│  ┌───────────────────────┐  │# Example: AWS Elastic Beanstalk

│  │  SQLite per session   │  │environment:

│  │  data/sessions/*.db   │  │  - GEMINI_API_KEY: ${GEMINI_KEY}

│  └───────────────────────┘  │  - DB_PATH: /data/sessions

└─────────────────────────────┘scaling:

```  min_instances: 1

  max_instances: 5

### Production (Docker Compose)```



```---

┌──────────────────┐    ┌──────────────────┐

│  Load Balancer   │───▶│  API (x4)        │## Future Enhancements (Phase 2)

│  (nginx)         │    │  Gunicorn        │

└──────────────────┘    │  + Uvicorn       │### Advanced RAG

                        └────────┬─────────┘- ChromaDB for persistent vector storage

                                 │- Cross-encoder reranking

        ┌────────────────────────┼─────────────────┐- Hybrid search (semantic + keyword)

        ↓                        ↓                 ↓- Metadata filtering

┌──────────────┐      ┌──────────────┐  ┌──────────────┐

│  ChromaDB    │      │  Redis       │  │  PostgreSQL  │### Emotion Detection

│  (vectors)   │      │  (cache)     │  │  (history)   │- Transformer-based models (BERT)

└──────────────┘      └──────────────┘  └──────────────┘- Multi-label classification

        ↓                        ↓                 ↓- Sentiment intensity scoring

┌──────────────────────────────────────────────────────┐

│              Monitoring (Prometheus + Grafana)       │### Distributed System

└──────────────────────────────────────────────────────┘- Redis for shared memory

```- PostgreSQL for persistence

- Message queue (RabbitMQ)

---- Horizontal scaling



## Performance Characteristics### Monitoring

- Prometheus metrics

### Latency (Typical)- Grafana dashboards

- OpenTelemetry tracing

```- Alert system

Component              | Latency

-----------------------|-------------

Emotion Detection      | <5ms

Embedding Generation   | 10-50ms (per message)## Troubleshooting Guide

RAG Retrieval          | 10-100ms (depends on DB size)

Cross-Encoder Rerank   | 5-20ms (for 50→10)### Common Issues

Gemini API Call        | 1-3s (network + generation)

Database Write         | 5-10ms**High Memory Usage**

Total (non-streaming)  | 1.5-4s```bash

```# Solution: Reduce working memory size

# In .env:

### ThroughputMAX_WORKING_MEMORY_SIZE=10

```

```

Concurrent Requests: 5 (rate limited at Gemini client)**Slow Responses**

Requests/min: ~100 (limited by Gemini API)```bash

Messages stored/sec: 200+# Solution: Reduce RAG top-k

RAG searches/sec: 100+RAG_TOP_K=1

```

# Or use faster model

### StorageGEMINI_MODEL=gemini-1.5-flash

```

```

SQLite per session: ~1-10 MB (depends on conversation length)**Database Locked**

Embedding storage: ~1.5 KB per message (384 floats × 4 bytes)```bash

ChromaDB index: ~2x raw embedding size# Solution: Close stale connections

```sqlite3 data/sessions/chat.db "PRAGMA journal_mode=WAL;"

```

---

**Embedding Errors**

## Security Considerations```bash

# Solution: Clear model cache

1. **API Key Management**rm -rf ~/.cache/torch/sentence_transformers/

   - Store in `.env` (not in code)```

   - Never commit `.env` to git

   - Use environment-specific keys---



2. **Session Isolation**## Performance Tuning

   - Each chat_id gets separate SQLite DB

   - No cross-session data leakage### For Speed

   - Sessions auto-cleanup via TTL (if Redis enabled)```env

EMBEDDING_MODEL=all-MiniLM-L6-v2  # Fastest

3. **Input Validation**RAG_TOP_K=1

   - Pydantic models validate all inputsMAX_WORKING_MEMORY_SIZE=10

   - SQL injection prevented (parameterized queries)SUMMARIZE_AFTER_MESSAGES=30

   - Token limits prevent resource exhaustion```



4. **Rate Limiting**### For Quality

   - Gemini client: max 5 concurrent```env

   - Can add API-level rate limiting with FastAPI middlewareEMBEDDING_MODEL=all-mpnet-base-v2  # Better quality

RAG_TOP_K=5

---MAX_WORKING_MEMORY_SIZE=30

SUMMARIZE_AFTER_MESSAGES=15

## Troubleshooting```



### Common Issues### For Cost Optimization

```env

**High Memory Usage**:GEMINI_MODEL=gemini-1.5-flash  # Cheaper

- Reduce `MAX_WORKING_MEMORY_SIZE`SYSTEM_TOKEN_PERCENT=15

- Enable Redis for distributed memoryRAG_TOKEN_PERCENT=20

- Clear old session databases```



**Slow RAG Retrieval**:---

- Enable `ENABLE_CHROMADB` for HNSW indices

- Reduce `RAG_TOP_K`**This architecture is designed to be production-ready, scalable, and easy to extend!**

- Enable `ENABLE_RERANKING` for better accuracy with fewer candidates

**Database Corruption**:
```bash
# Backup and delete
mv data/sessions/*.db data/sessions/backup/
# Restart server
```

**Gemini Rate Limits**:
- Upgrade to paid tier
- Reduce concurrent requests
- Add exponential backoff (already implemented)

---

## Future Enhancements

### Planned Features

1. **Multi-LLM Support**
   - OpenAI, Anthropic, local models
   - Fallback chains

2. **Advanced Summarization**
   - Hierarchical summaries
   - Key moment extraction
   - Relationship graphs

3. **Memory Compression**
   - Adaptive context windows
   - Importance-based pruning
   - Smart summarization triggers

4. **Multi-modal Embeddings**
   - Image understanding
   - Voice input
   - Document processing

---

For implementation details, see the source code in `app/`. For usage instructions, see **QUICKSTART.md**.
