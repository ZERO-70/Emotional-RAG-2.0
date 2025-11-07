# Quick Start Guide# Quick Start Guide



Get the Emotional RAG Backend running with SillyTavern in under 5 minutes.## Overview

This guide will help you get the Emotional RAG Backend running with SillyTavern in under 5 minutes.

## Prerequisites

## Prerequisites

- Python 3.10 or higher- Python 3.10 or higher

- Google Gemini API key ([Get one free](https://makersuite.google.com/app/apikey))- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

- 2GB free disk space- 2GB free disk space (for models and data)



------



## Installation## Step-by-Step Setup



### 1. Setup Python Environment### 1. Install Dependencies



```bash```bash

# Navigate to project# Navigate to project directory

cd persona2cd emotional-rag-backend



# Create virtual environment# Create virtual environment

python3 -m venv venvpython3 -m venv venv



# Activate it# Activate virtual environment

source venv/bin/activate  # Linux/Mac# On Linux/Mac:

# venv\Scripts\activate   # Windowssource venv/bin/activate

# On Windows:

# Install dependencies# venv\Scripts\activate

pip install -r requirements.txt

```# Install packages

pip install -r requirements.txt

**First run**: Downloads embedding model (~80MB) automatically.```



### 2. Configure API Key**Note**: First install will download the sentence-transformers model (~80MB) automatically.



```bash### 2. Configure Environment

# Copy environment template

cp .env.example .env```bash

# Copy example environment file

# Edit and add your Gemini API keycp .env.example .env

nano .env  # or use your preferred editor

```# Edit .env and add your Gemini API key

# Use your favorite editor (nano, vim, vscode, etc.)

**Required**: Set `GEMINI_API_KEY=your-actual-key-here`nano .env

```

### 3. Start the Server

**Required**: Set your `GEMINI_API_KEY` in the `.env` file.

```bash

# Make script executable (first time only)### 3. Run the Backend

chmod +x run.sh

```bash

# Start server# Make run script executable

./run.shchmod +x run.sh

```

# Start the server

Server starts at: **http://localhost:8001**./run.sh

```

**Alternative**: Direct launch

```bashThe server will start at `http://localhost:8001`

uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

```**Alternative**: Run directly with uvicorn

```bash

### 4. Verify It's Runninguvicorn app.main:app --reload --host 0.0.0.0 --port 8001

```

```bash

# Test health check### 4. Verify Installation

curl http://localhost:8001/health

Open another terminal and test:

# Expected response:

# {"status":"healthy","gemini_api":true,...}```bash

```# Test health endpoint

curl http://localhost:8001/health

Or visit: **http://localhost:8001/docs** (interactive API docs)

# Should return:

---# {"status":"healthy","gemini_api":true,"database":true,"memory_sessions":0}

```

## SillyTavern Setup

Or visit in browser: http://localhost:8001/docs

### Configure API Connection

---

1. Open SillyTavern at `http://localhost:8000`

2. Click **☰ menu** → **API Connections**## SillyTavern Configuration

3. Select:

   - **API**: `Chat Completion`### Method 1: Using SillyTavern UI (Recommended)

   - **Source**: `Custom (OpenAI-compatible)`

4. Enter connection details:1. **Open SillyTavern** at `http://localhost:8000` (SillyTavern's own server)

   - **API URL**: `http://localhost:8001/v1` ⚠️ **Port 8001**2. Click the **hamburger menu** (☰) in the top-left → **API Connections**

   - **API Key**: `sk-anything` (any dummy value)3. Select **API**: `Chat Completion`

   - **Model**: `gemini-2.0-flash-exp`4. Select **Chat Completion Source**: `Custom (OpenAI-compatible)`

5. Click **Test** → Should show ✓ green checkmark5. **Configure the connection**:

6. Click **Connect**   - **API URL**: `http://localhost:8001/v1` (note: port 8001, not 8000)

   - **API Key**: `sk-anything` (put any dummy key, it's not validated)

**Port Confusion Fix**:   - **Model**: `gemini-2.0-flash-exp` (or whatever model you set in `.env`)

- SillyTavern UI: Port **8000**6. Click the **Test** button - should show a green checkmark ✓

- This Backend: Port **8001** (use this in API URL!)7. Click **Connect**



### Test the Connection**Important**: 

- SillyTavern runs on port **8000**

Start chatting in SillyTavern! The bot should:- Your backend runs on port **8001** 

- ✅ Respond using Gemini- Make sure to use `http://localhost:8001/v1` in the API URL setting

- ✅ Remember conversation context

- ✅ Maintain persona across messages### Method 2: Manual Configuration



---Edit SillyTavern's `config.yaml`:



## Basic Configuration```yaml

api_type: openai

Edit `.env` to customize behavior:api_url: http://localhost:8001/v1

api_key: ""

### Essential Settingsmodel: gemini-2.0-flash-exp

```

```env

# API Configuration---

GEMINI_API_KEY=your-key-here         # REQUIRED

GEMINI_MODEL=gemini-2.0-flash-exp    # Or gemini-1.5-pro## Testing the System

PORT=8001                            # Server port

### Test 1: Basic Chat

# Memory Settings

MAX_WORKING_MEMORY_SIZE=20           # Messages in RAM```bash

SUMMARIZE_AFTER_MESSAGES=20          # Auto-summarize after N messagescd examples

RAG_TOP_K=3                          # Retrieved memory chunkspython test_usage.py

``````



### Phase 2 Features (Optional)This will run comprehensive tests including:

- Basic chat completion

**Enable for better performance**:- Multi-turn conversation

- Streaming responses

```env- Memory retrieval

ENABLE_CHROMADB=true              # Better vector search

ENABLE_RERANKING=true             # More accurate retrieval### Test 2: Manual Test

ENABLE_TRANSFORMER_EMOTIONS=true  # Advanced emotion detection

ENABLE_METRICS=true               # Prometheus metrics```bash

```curl -X POST http://localhost:8001/v1/chat/completions \

  -H "Content-Type: application/json" \

**Requires external services** (disable by default):  -d '{

    "model": "gemini-2.0-flash-exp",

```env    "messages": [

ENABLE_REDIS=false                # Needs Redis server      {"role": "system", "content": "You are a helpful assistant."},

ENABLE_POSTGRESQL=false           # Needs PostgreSQL server      {"role": "user", "content": "Hello!"}

```    ],

    "user": "test_chat"

---  }'

```

## Testing

### Test 3: In SillyTavern

### Quick Test Commands

1. Load a character card

```bash2. Start chatting normally

# Test chat completion3. After 20+ messages, the system will automatically:

curl -X POST http://localhost:8001/v1/chat/completions \   - Summarize old messages

  -H "Content-Type: application/json" \   - Retrieve relevant context

  -d '{   - Never forget the persona

    "model": "gemini-2.0-flash-exp",

    "messages": [{"role": "user", "content": "Hello!"}]---

  }'

## Verification Checklist

# Check available models

curl http://localhost:8001/v1/models✅ Server starts without errors  

✅ Health endpoint returns "healthy"  

# View health status✅ SillyTavern connection test succeeds  

curl http://localhost:8001/health✅ First message generates response  

```✅ Character details are remembered  

✅ Session data saved to `data/sessions/`  

### Memory Diagnostics

---

```bash

# Check stored conversations## Common Issues

python debug_memory.py

### Issue: Import errors when starting

# Test RAG retrieval

python debug_memory.py --chat-id default --test-query "my name"**Solution**: Make sure you're in the virtual environment

``````bash

source venv/bin/activate  # Linux/Mac

### Run Test Suite# or

venv\Scripts\activate     # Windows

```bash```

# All tests

pytest### Issue: "Gemini API connection failed"



# Specific test**Solutions**:

pytest tests/test_memory.py -v1. Check your API key in `.env`

2. Verify API key is active at https://makersuite.google.com/

# With coverage3. Check internet connection

pytest --cov=app tests/4. Make sure you have the latest `google-genai` SDK installed: `pip install -U google-genai`

```

### Issue: SillyTavern can't connect

---

**Solutions**:

## Monitoring1. Verify backend is running: `curl http://localhost:8001/health`

2. Make sure SillyTavern is using the correct URL: `http://localhost:8001/v1` (port **8001**, not 8000)

### View Logs3. Check firewall isn't blocking port 8001

4. If running on different machine, change `HOST` in `.env` to `0.0.0.0`

```bash5. Ensure both SillyTavern and your backend are running (SillyTavern on port 8000, backend on port 8001)

# Real-time logs

tail -f logs/app.log### Issue: Port conflict



# Pretty print JSON logs**Solution**: If you get "address already in use" error:

tail -f logs/app.log | jq .1. SillyTavern uses port 8000 by default

2. This backend uses port 8001 to avoid conflicts

# Filter errors3. You can change the backend port in `.env` by setting `PORT=8002` (or any other free port)

grep ERROR logs/app.log4. Remember to update the API URL in SillyTavern to match!

```

### Issue: Slow responses

### Check Session Data

**Solutions**:

```bash1. Reduce `RAG_TOP_K` in `.env` (try 1 or 2)

# List active sessions2. Reduce `MAX_WORKING_MEMORY_SIZE` to 10

ls data/sessions/3. Use `gemini-1.5-flash` instead of `gemini-1.5-pro`



# Query a session database### Issue: High memory usage

sqlite3 data/sessions/default.db

SELECT COUNT(*) FROM messages;**Solution**: Embeddings are cached in RAM. Restart periodically or:

.quit```python

```# In .env, reduce:

MAX_WORKING_MEMORY_SIZE=10

### Metrics Endpoint```



If `ENABLE_METRICS=true`:---



```bash## Next Steps

# Prometheus format metrics

curl http://localhost:8001/metrics### Optimize for Your Use Case

```

**For RP/Creative Writing**:

---```env

TEMPERATURE=0.9

## TroubleshootingRAG_TOP_K=3

SYSTEM_TOKEN_PERCENT=25  # More persona context

### Server Won't StartGEMINI_MODEL=gemini-2.0-flash-exp  # Fast and creative

```

**Port already in use**:

```bash**For Informational/Tutoring**:

# Change port in .env```env

PORT=8002TEMPERATURE=0.5

RAG_TOP_K=5

# Or kill process on 8001RAG_TOKEN_PERCENT=30  # More retrieved context

lsof -ti:8001 | xargs kill -9GEMINI_MODEL=gemini-2.0-flash-exp

``````



**Missing dependencies**:### Enable Advanced Features (Phase 2)

```bash

pip install -r requirements.txt --force-reinstallComing soon:

```- ChromaDB for persistent embeddings

- Cross-encoder reranking

### SillyTavern Connection Failed- Transformer-based emotion detection

- Redis for distributed sessions

**Wrong URL**:

- ❌ `http://localhost:8000/v1` (SillyTavern's port)---

- ✅ `http://localhost:8001/v1` (Our backend port)

## Data Management

**Backend not running**:

```bash### View Session Data

# Check if server is up

curl http://localhost:8001/health```bash

```# List all sessions

ls data/sessions/

**Firewall blocking**:

```bash# Query a session database

# Allow port 8001sqlite3 data/sessions/<chat_id>.db

sudo ufw allow 8001

```sqlite> SELECT COUNT(*) FROM messages;

sqlite> SELECT * FROM messages ORDER BY timestamp DESC LIMIT 5;

### Gemini API Errorssqlite> SELECT * FROM personas;

```

**429 Rate Limit**:

- Free tier: 50 requests/day### Backup Sessions

- Wait or upgrade to paid tier

```bash

**Invalid API Key**:# Backup all session data

```bashtar -czf backup_$(date +%Y%m%d).tar.gz data/

# Verify key in .env```

grep GEMINI_API_KEY .env

### Clear Old Sessions

# Test directly

curl https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY```bash

```# Remove sessions older than 30 days

find data/sessions/ -name "*.db" -mtime +30 -delete

### Memory Issues```



**Bot forgets information**:---

1. Check if messages are being stored:

   ```bash## Performance Tips

   python debug_memory.py --chat-id default

   ```1. **Use SSD** for `data/sessions/` directory

2. Verify embeddings are generated (should show "With embeddings: X")2. **Adjust token budgets** based on your needs

3. Test RAG retrieval:3. **Monitor logs** in `logs/app.log`

   ```bash4. **Track costs** via `/health` endpoint

   python debug_memory.py --chat-id default --test-query "remember"5. **Summarize frequently** for long conversations (set `SUMMARIZE_AFTER_MESSAGES=15`)

   ```

---

**Database corruption**:

```bash## Getting Help

# Delete and restart

rm data/sessions/*.db- **Documentation**: See main `README.md`

# Restart server- **Logs**: Check `logs/app.log` for errors

```- **API Docs**: Visit `http://localhost:8001/docs`

- **Health Check**: `curl http://localhost:8001/health`

---- **Issues**: Open a GitHub issue with logs



## Advanced Setup---



### Docker Deployment## Success Indicators



```bashYou'll know it's working when:

# Build image

docker build -t emotional-rag-backend .✨ Character never forgets core personality  

✨ References past conversations accurately  

# Run container✨ Adapts to emotional context  

docker run -p 8001:8001 --env-file .env emotional-rag-backend✨ Responses stay consistent after 100+ messages  

```✨ No "I don't recall" or persona drift  



### Full Stack with Docker Compose---



```bash**Enjoy your production-ready emotional RAG backend!** 🚀

# Start all services (Redis, PostgreSQL, Prometheus, Grafana)
docker-compose up -d

# Enable services in .env
ENABLE_REDIS=true
ENABLE_POSTGRESQL=true
POSTGRES_URL=postgresql+asyncpg://postgres:password@localhost:5432/emotional_rag
```

### Production Deployment

```bash
# Use gunicorn for production
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

---

## Next Steps

- 📖 Read **ARCHITECTURE.md** for system design details
- 🔧 Customize token budgets in `.env`
- 📊 Enable Phase 2 features for better performance
- 🐳 Deploy with Docker for production
- 📈 Set up Grafana dashboards for monitoring

---

## Quick Reference

| Component | Default Port | URL |
|-----------|-------------|-----|
| This Backend | 8001 | http://localhost:8001 |
| SillyTavern | 8000 | http://localhost:8000 |
| API Docs | 8001 | http://localhost:8001/docs |
| Health Check | 8001 | http://localhost:8001/health |
| Metrics | 8001 | http://localhost:8001/metrics |

**Important Files**:
- `.env` - Configuration
- `logs/app.log` - Application logs
- `data/sessions/*.db` - Conversation storage
- `requirements.txt` - Python dependencies

**Useful Commands**:
```bash
./run.sh                 # Start server
python debug_memory.py   # Check memory storage
pytest                   # Run tests
docker-compose up -d     # Start full stack
```

---

**Need help?** Check the logs first: `tail -f logs/app.log`
