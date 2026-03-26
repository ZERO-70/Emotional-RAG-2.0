# Quick Start Guide

This guide gets the Emotional RAG Backend running with SillyTavern using the current codebase defaults.

## Prerequisites

- Python 3.10+
- One provider API key:
  - OpenRouter (default provider)
  - Gemini
  - Mancer
- About 2 GB free disk space (dependencies, model cache, runtime data)

## 1) Setup

```bash
cd Emotional-RAG-2.0
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) Configure Environment

Edit `.env` and set provider + key.

### Option A: OpenRouter (default)

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
PORT=8001
```

### Option B: Gemini

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8001
```

### Option C: Mancer

```env
LLM_PROVIDER=mancer
MANCER_API_KEY=your_mancer_api_key_here
PORT=8001
```

Important notes:

- `run.sh` launches on port 8001.
- App settings default to port 8000 if you launch uvicorn manually without `--port`.
- For SillyTavern integration in this repo, use backend port 8001.

## 3) Run Backend

### Recommended

```bash
./run.sh
```

### Alternative

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 4) Verify Backend

```bash
curl http://localhost:8001/health
```

Expected shape:

```json
{
  "status": "healthy",
  "database": true,
  "memory_sessions": 0,
  "llm_provider": "openrouter",
  "openrouter_api": true
}
```

Also available:

- API docs: `http://localhost:8001/docs`
- Root info: `http://localhost:8001/`

## 5) Configure SillyTavern

In SillyTavern API settings:

- API: Chat Completion
- Source: Custom (OpenAI-compatible)
- API URL: `http://localhost:8001/v1`
- API key: any placeholder value accepted by SillyTavern UI
- Model: valid model ID for selected provider

Port reminder:

- SillyTavern UI commonly runs on 8000.
- This backend should be configured as 8001 in API URL.

## 6) Quick API Test

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-2-9b-it:free",
    "messages": [
      {"role": "user", "content": "Hello, please introduce yourself."}
    ],
    "user": "test_chat_001",
    "stream": false
  }'
```

## Optional Feature Flags

Common toggles in `.env`:

```env
ENABLE_CHROMADB=true
INGEST_KNOWLEDGE_BASE=true
STORE_CHAT_EMBEDDINGS=false
ENABLE_RERANKING=true
ENABLE_TRANSFORMER_EMOTIONS=true
ENABLE_REDIS=false
ENABLE_POSTGRESQL=false
ENABLE_METRICS=false
```

## Troubleshooting

- Startup fails due missing key:
  - Ensure key matches selected `LLM_PROVIDER`.
- SillyTavern cannot connect:
  - Confirm backend on `http://localhost:8001/health`.
  - Confirm API URL includes `/v1`.
- Retrieval seems empty:
  - Check `knowledge_base/` has supported files (`.txt`, `.json`).
  - Confirm `INGEST_KNOWLEDGE_BASE=true` and `ENABLE_CHROMADB=true`.
- Logs:
  - Check `logs/app.log`.
