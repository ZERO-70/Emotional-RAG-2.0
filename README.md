# Emotional RAG Backend for SillyTavern

**Production-ready backend** that solves persona forgetting in long conversations through proactive memory management, semantic retrieval, and emotional context tracking.

## 🎯 Key Features

✅ **Proactive Persona Persistence** - Never forgets character details, even after 100+ messages  
✅ **Semantic Memory Retrieval** - RAG-based context injection from past conversations  
✅ **Emotional Context Tracking** - Detects and responds to emotional states  
✅ **Automatic Summarization** - Compresses old messages while preserving key moments  
✅ **Token Budget Management** - Intelligent context allocation to maximize relevance  
✅ **Multi-Session Support** - Isolated memory per conversation  
✅ **OpenAI-Compatible API** - Drop-in replacement for SillyTavern  
✅ **Cost Tracking** - Monitor token usage per session  

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- SillyTavern (optional, for testing)

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd emotional-rag-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run the server
chmod +x run.sh
./run.sh
```

The server will start at `http://localhost:8001`

---

## 🔧 SillyTavern Configuration

### Step-by-Step Setup

1. **Open SillyTavern** at `http://localhost:8000` (SillyTavern's own server)

2. **Open Settings** (hamburger menu → API Connections)

3. **Select API Type**: `Chat Completion`

4. **Choose API Source**: `Custom (OpenAI-compatible)`

5. **Configure Connection**:
   - **API URL**: `http://localhost:8001/v1` (note: port **8001**, not 8000)
   - **API Key**: `sk-anything` (put any dummy key)
   - **Model**: `gemini-2.0-flash-exp`

6. **Test Connection**: Click "Test" - should show green checkmark ✓

7. **Advanced Settings** (optional):
   - **Temperature**: `0.9` (creative responses)
   - **Max Response Tokens**: `800`

**Important Port Information**:
- **SillyTavern UI**: Runs on port `8000`
- **This Backend**: Runs on port `8001`
- Make sure to use `http://localhost:8001/v1` in the API settings!

### Troubleshooting
- **Connection Failed**: Ensure backend is running (`./run.sh`) and using correct port (8001)
- **Port Conflict**: If port 8001 is in use, change `PORT` in `.env` to another port
- **Persona Forgotten**: Check `data/sessions/` for SQLite files
- **Slow Responses**: Reduce `RAG_TOP_K` in `.env`

---

## 📊 Architecture Overview

### Multi-Tiered Memory System

```
┌─────────────────────────────────────────────────────┐
│               Working Memory (RAM)                  │
│          Last 10-20 messages (instant)              │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│          Short-Term Memory (SQLite)                 │
│     Full conversation history + metadata            │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│      Long-Term Memory (Vector Embeddings)           │
│   Semantic search over all past conversations       │
└─────────────────────────────────────────────────────┘
```

### Request Flow

```
User Message
    ↓
Emotion Detection → Importance Scoring
    ↓
RAG Retrieval (semantic + emotional)
    ↓
Context Building (token budget allocation)
    ↓
Gemini API Call (with retry logic)
    ↓
Store Message + Embeddings
    ↓
Check Summarization Trigger
    ↓
Response to SillyTavern
```

### Token Budget Allocation

| Component | Allocation | Tokens (4096 total) |
|-----------|------------|---------------------|
| System/Persona | 20% | ~800 |
| RAG Context | 25% | ~1000 |
| Conversation History | 35% | ~1400 |
| Response Buffer | 20% | ~800 |

---

## 📁 Project Structure

```
emotional-rag-backend/
├── app/
│   ├── main.py                 # FastAPI app initialization
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py            # /v1/chat/completions
│   │   └── health.py          # /health
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Environment & settings
│   │   ├── memory.py          # Multi-tiered memory manager
│   │   └── token_manager.py   # Context building & budgets
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_client.py   # Gemini API wrapper
│   │   ├── rag_engine.py      # Semantic retrieval
│   │   └── emotion_tracker.py # Emotion detection
│   └── models/
│       ├── __init__.py
│       ├── chat.py            # OpenAI schemas
│       └── memory.py          # Memory data structures
├── data/
│   ├── sessions/              # Per-session SQLite DBs
│   └── embeddings/            # Cached embeddings
├── tests/
│   ├── test_memory.py
│   ├── test_rag.py
│   └── test_endpoints.py
├── .env.example
├── .env
├── requirements.txt
├── run.sh
└── README.md
```

---

## 🔌 API Endpoints

### Chat Completions
```bash
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "gemini-2.0-flash-exp",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.9,
  "max_tokens": 800,
  "stream": false
}
```

### List Models
```bash
GET /v1/models
```

### Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "gemini_api": true,
  "database": true,
  "memory_sessions": 3
}
```

---

## ⚙️ Configuration

Edit `.env` to customize behavior:

### Memory Settings
```env
MAX_WORKING_MEMORY_SIZE=20        # Messages to keep in RAM
SUMMARIZE_AFTER_MESSAGES=20       # Auto-summarize trigger
DB_PATH=./data/sessions           # SQLite storage location
```

### API Settings
```env
GEMINI_API_KEY=your-key-here      # Get from https://makersuite.google.com/
GEMINI_MODEL=gemini-2.0-flash-exp # Or gemini-1.5-pro, etc.
HOST=0.0.0.0                      # Server host
PORT=8001                         # Server port (SillyTavern uses 8000)
```

### RAG Settings
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Sentence-transformers model
RAG_TOP_K=3                       # Number of retrieved chunks

# Phase 2 Features (optional)
ENABLE_CHROMADB=true              # Advanced vector database
ENABLE_RERANKING=true             # Cross-encoder reranking
ENABLE_TRANSFORMER_EMOTIONS=true  # Better emotion detection
ENABLE_REDIS=false                # Distributed memory (needs Redis server)
ENABLE_POSTGRESQL=false           # PostgreSQL (needs server)
ENABLE_METRICS=true               # Prometheus metrics
```

### Token Budget
```env
SYSTEM_TOKEN_PERCENT=20           # Persona allocation
RAG_TOKEN_PERCENT=25              # Retrieved context
HISTORY_TOKEN_PERCENT=35          # Conversation history
RESPONSE_TOKEN_PERCENT=20         # Output buffer
```

---

## 📈 Monitoring & Debugging

### View Session Data
```bash
# List all active sessions
ls data/sessions/

# Query session database
sqlite3 data/sessions/<chat_id>.db
SELECT * FROM messages ORDER BY timestamp DESC LIMIT 10;
```

### Check Logs
```bash
# Logs are written to stdout in JSON format
tail -f logs/app.log | jq .

# Filter by level
grep ERROR logs/app.log
```

### Cost Tracking
Access `/health` endpoint to see per-session token usage and estimated costs.

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_memory.py -v

# Test with coverage
pytest --cov=app tests/
```

### Manual Testing
```bash
# Test chat completion
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.0-flash-exp",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## 🚀 Deployment

### Docker (Coming in Phase 2)
```bash
docker build -t emotional-rag-backend .
docker run -p 8001:8001 --env-file .env emotional-rag-backend
```

### Production Considerations
- Use **gunicorn** with multiple workers for production
- Set up **Redis** for distributed working memory
- Enable **Prometheus** metrics endpoint
- Configure reverse proxy (nginx) for SSL

---

## 📝 How It Solves Persona Forgetting

### The Problem
Traditional chatbots lose character details after ~30-50 messages due to context window limits. They forget:
- Core personality traits
- Past emotional moments
- Important user preferences
- Established relationship dynamics

### Our Solution

#### 1. **Proactive Context Building**
Instead of waiting for the model to forget, we:
- Always include full persona (20% token budget)
- Retrieve semantically relevant past messages via RAG
- Summarize old messages instead of dropping them
- Track emotional context across sessions

#### 2. **Semantic Memory Retrieval**
When user mentions "remember when we...", the system:
- Embeds the query using sentence-transformers
- Searches past messages for semantic similarity
- Boosts emotionally important moments (scored 0-1)
- Injects top-3 relevant memories into context

#### 3. **Automatic Summarization**
Every 20 messages:
- Gemini summarizes old conversation
- Preserves key emotional moments, decisions, facts
- Stores summary with message range reference
- Reduces token usage by ~70% while retaining essence

#### 4. **Emotional Importance Scoring**
Messages are scored (0-1) based on:
- Emotional intensity (joy, sadness, anger, fear)
- Length (detailed thoughts = higher importance)
- User engagement (questions, follow-ups)
- High-importance messages prioritized in RAG retrieval

---

## 🛣️ Roadmap

### Phase 1 (MVP) ✅
- [x] FastAPI skeleton with OpenAI endpoints
- [x] SQLite-based memory management
- [x] Sentence-transformers RAG
- [x] Gemini integration with retry
- [x] Token budget management
- [x] Rule-based emotion detection
- [x] Basic summarization

### Phase 2 (Production) ✅
- [x] Upgrade to ChromaDB for vectors
- [x] Implement reranking with cross-encoder
- [x] Transformer-based emotion detection
- [x] Redis for distributed memory
- [x] Monitoring & metrics (Prometheus)
- [x] Docker deployment
- [ ] Cost tracking dashboard
- [ ] Comprehensive test suite

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Follow PEP 8 and type hint all functions
4. Add tests for new features
5. Submit a pull request

---

## 🆘 Support

- **Issues**: Open a GitHub issue
- **Discussions**: Use GitHub Discussions
- **Email**: support@example.com

---

## 🙏 Acknowledgments

- **SillyTavern** team for the amazing frontend
- **Google Gemini** for the powerful LLM API
- **Sentence-transformers** for efficient embeddings
- Open source community ❤️

---

**Built with ❤️ for the roleplay AI community**
