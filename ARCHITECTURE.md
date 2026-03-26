# Architecture Documentation

## Overview

Emotional RAG Backend is a FastAPI service that adds long-term memory and retrieval around chat completions for roleplay workflows.

Core goals:

- Preserve persona and important context across long chats
- Retrieve semantically relevant memory on each turn
- Track emotional context to improve retrieval relevance
- Expose OpenAI-compatible endpoints for SillyTavern

## High-Level Components

- API Layer: request handling and OpenAI-compatible routes
- Memory Manager: working memory + persistent session storage + retrieval orchestration
- Retrieval Stack: sentence-transformers embeddings, ChromaDB (or SQLite fallback), reranker optional
- LLM Abstraction: provider-agnostic completion interface (OpenRouter, Gemini, Mancer)
- Knowledge Ingestion: file ingestion pipeline into dedicated knowledge-base vector collection

## Runtime Topology

```text
SillyTavern (frontend)
   -> OpenAI-compatible HTTP API
FastAPI app (app/main.py)
   -> routes/chat.py, routes/health.py
   -> MemoryManager (app/core/memory.py)
      -> working memory (RAM deque per chat_id)
      -> SQLite session DB (data/sessions/{chat_id}.db)
      -> ChromaDB chat collections (if enabled)
   -> KnowledgeIngester (app/services/knowledge_ingester.py)
      -> ChromaDB collection: knowledge_base
   -> UnifiedLLMClient (provider selected by LLM_PROVIDER)
```

## Chat Request Lifecycle

1. Receive `POST /v1/chat/completions`.
2. Resolve `chat_id` from `request.user`.
3. Detect emotion from latest user message.
4. Ensure persona is available (store from system prompt if missing).
5. Retrieve chat memory context via semantic search.
6. Retrieve global knowledge-base context from `knowledge_base` collection.
7. Allocate token budget and build final context messages.
8. Call provider through unified LLM client.
9. Persist user and assistant messages (plus optional embeddings).
10. Trigger background summarization when threshold is met.

## Memory Model

### 1) Working Memory (RAM)

- In-process deque per `chat_id`
- Fast access to recent turns
- Size controlled by `MAX_WORKING_MEMORY_SIZE`

### 2) Session Persistence (SQLite)

- Per-session DB under `data/sessions`
- Stores messages, persona, summaries metadata
- Supports summarization checks and history persistence

### 3) Vector Retrieval

- Preferred: ChromaDB persistent store (`CHROMADB_PATH`)
- Fallback: embeddings as SQLite BLOBs when ChromaDB disabled

## Retrieval Layers

### Chat Memory Retrieval

- Query is embedded with sentence-transformers (`all-MiniLM-L6-v2`)
- Searches current chat collection
- Optional emotional boost and optional reranking
- Applies relevance threshold before prompt injection

### Knowledge Base Retrieval

- Uses separate ChromaDB collection named `knowledge_base`
- Ingests local files from `knowledge_base/`
- Supports `.txt` and chat-export `.json`
- Uses manifest hashing to avoid re-ingesting unchanged files

## LLM Provider Abstraction

`UnifiedLLMClient` wraps provider-specific clients:

- OpenRouter client
- Gemini client
- Mancer client

Selection is controlled by `LLM_PROVIDER` and associated API key variables.

## Configuration Highlights

- Server: `HOST`, `PORT`
- Retrieval: `RAG_TOP_K`, `EMBEDDING_MODEL`
- Memory: `MAX_WORKING_MEMORY_SIZE`, `SUMMARIZE_AFTER_MESSAGES`
- Feature flags:
  - `ENABLE_CHROMADB`
  - `INGEST_KNOWLEDGE_BASE`
  - `STORE_CHAT_EMBEDDINGS`
  - `ENABLE_RERANKING`
  - `ENABLE_TRANSFORMER_EMOTIONS`
  - `ENABLE_REDIS`
  - `ENABLE_POSTGRESQL`
  - `ENABLE_METRICS`

## APIs

Primary endpoints:

- `POST /v1/chat/completions`
- `GET /v1/models`
- `GET /health`
- `GET /metrics` (when enabled)

SillyTavern compatibility endpoints are implemented under `/api/...` in `app/routes/chat.py`.

## Data and Operations

Persistent runtime data:

- `data/sessions/` (SQLite session DBs)
- `data/chromadb/` (when ChromaDB enabled)
- `data/ingestion_manifest.json` (knowledge ingestion dedupe state)
- `logs/app.log` (structured logging)

Recommended backup scope:

- `data/sessions`
- `data/chromadb`
- `knowledge_base`
- `.env`

## Notes on Scale

- Current implementation already supports hybrid storage (SQLite + ChromaDB).
- PostgreSQL and Redis feature flags exist for future scaling paths, but migration procedures should be planned before production rollout.
