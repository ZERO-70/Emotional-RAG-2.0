# Emotional RAG Backend

Production FastAPI backend for long-running roleplay/chat sessions with persistent memory, semantic retrieval, emotional context, and OpenAI-compatible endpoints for SillyTavern.

## What This Project Does

- Preserves character/persona continuity across long conversations.
- Stores chat history per session and retrieves relevant past context via embeddings.
- Supports multiple LLM providers behind one unified interface.
- Exposes OpenAI-style chat endpoints plus SillyTavern compatibility routes.
- Optionally ingests a local knowledge base into a vector index for retrieval.

## Current Architecture (As Implemented)

This project currently uses a hybrid memory stack:

- Working memory (RAM): recent messages per `chat_id` in process.
- Session persistence (SQLite): per-session files under `data/sessions`.
- Vector retrieval:
  - ChromaDB when enabled (default in config).
  - SQLite BLOB fallback when ChromaDB is disabled.

Knowledge base retrieval is separate from chat-memory retrieval:

- A dedicated ChromaDB collection named `knowledge_base` is populated from local files.
- Chat memories are stored in per-chat ChromaDB collections (when ChromaDB is enabled).

## LLM Provider Support

Provider is selected through `LLM_PROVIDER`:

- `openrouter` (default)
- `gemini`
- `mancer`

The app initializes a unified LLM client in startup lifespan and routes all completions through it.

## Request Flow (High Level)

1. Receive `POST /v1/chat/completions`.
2. Use `request.user` as `chat_id` (session identity).
3. Detect emotion from latest user message.
4. Retrieve semantic memory context (chat-specific).
5. Retrieve additional knowledge-base context (global `knowledge_base` collection).
6. Build token-budgeted context.
7. Call selected LLM provider.
8. Persist user/assistant messages and optional embeddings.
9. Trigger summarization when threshold is reached.

## Knowledge Base Ingestion

When enabled (`ENABLE_CHROMADB=true` and `INGEST_KNOWLEDGE_BASE=true`):

- Startup ingestion scans `knowledge_base/`.
- Supported sources:
  - `.json` (chat export parsing)
  - `.txt` (document chunking)
- Dedupe is manifest-based using hashes in `data/ingestion_manifest.json`.
- Optional file watcher auto-ingests changed/new files while server is running.

## Ports and Startup Behavior

There are two common startup paths:

- `./run.sh` launches on port `8001` (hardcoded in script).
- `uvicorn app.main:app ...` uses your chosen port; app config default is `8000`, while `.env.example` sets `PORT=8001`.

Recommended for SillyTavern compatibility in this repo: run backend on `8001`.

## Quick Start

### 1) Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2) Configure `.env`

At minimum, configure your provider and API key:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
PORT=8001
```

For Gemini:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

For Mancer:

```env
LLM_PROVIDER=mancer
MANCER_API_KEY=your_key_here
```

### 3) Run

Option A:

```bash
./run.sh
```

Option B:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 4) Verify

```bash
curl http://localhost:8001/health
```

## SillyTavern Configuration

- API type: Chat Completion
- Source: Custom (OpenAI-compatible)
- API URL: `http://localhost:8001/v1`
- API key: any placeholder value accepted by SillyTavern UI
- Model: a model ID available for your selected provider

Important:

- SillyTavern UI commonly runs on `8000`.
- This backend should be configured on `8001` in the API URL.

## API Endpoints

Primary:

- `POST /v1/chat/completions`
- `GET /v1/models`
- `GET /health`
- `GET /metrics` (when metrics are enabled)

SillyTavern compatibility routes are also implemented under `/api/...`.

## Key Configuration Flags

Memory and retrieval:

- `MAX_WORKING_MEMORY_SIZE`
- `SUMMARIZE_AFTER_MESSAGES`
- `RAG_TOP_K`
- `STORE_CHAT_EMBEDDINGS`

Phase-2 feature flags:

- `ENABLE_CHROMADB`
- `INGEST_KNOWLEDGE_BASE`
- `RESET_INGESTION_ON_START`
- `ENABLE_RERANKING`
- `ENABLE_TRANSFORMER_EMOTIONS`
- `ENABLE_REDIS`
- `ENABLE_POSTGRESQL`
- `ENABLE_METRICS`

## Testing

```bash
pytest tests/ -v
```

Targeted suites available:

- `tests/test_api.py`
- `tests/test_memory.py`
- `tests/test_emotion.py`

## Repository Layout (Current Workspace)

```text
app/
  core/
    config.py
    memory.py
    token_manager.py
  routes/
    chat.py
    health.py
  services/
    chromadb_store.py
    emotion_tracker.py
    gemini_client.py
    knowledge_ingester.py
    llm_provider.py
    mancer_client.py
    metrics.py
    openrouter_client.py
    rag_engine.py
    redis_memory.py
    reranker.py
    transformer_emotions.py
data/
  ingestion_manifest.json
  sessions/
knowledge_base/
tests/
```

## Operational Notes

- Logs are written to `logs/app.log` in JSON or text format depending on `LOG_FORMAT`.
- Session data is isolated by `chat_id` (`request.user` in chat-completion requests).
- ChromaDB is persistent on disk at `CHROMADB_PATH` when enabled.

## Known Gaps and Practical Next Steps

- PostgreSQL and Redis flags exist, but production migration workflows are not fully documented in this README.
- For sustained growth, define backup/restore procedures for:
  - `data/sessions`
  - `data/chromadb`
  - `knowledge_base`
  - `.env` and deployment config

## License

MIT (see `LICENSE`).
