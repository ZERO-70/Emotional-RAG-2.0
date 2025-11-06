# Quick Start Guide

## Overview
This guide will help you get the Emotional RAG Backend running with SillyTavern in under 5 minutes.

## Prerequisites
- Python 3.10 or higher
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- 2GB free disk space (for models and data)

---

## Step-by-Step Setup

### 1. Install Dependencies

```bash
# Navigate to project directory
cd emotional-rag-backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

**Note**: First install will download the sentence-transformers model (~80MB) automatically.

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your Gemini API key
# Use your favorite editor (nano, vim, vscode, etc.)
nano .env
```

**Required**: Set your `GEMINI_API_KEY` in the `.env` file.

### 3. Run the Backend

```bash
# Make run script executable
chmod +x run.sh

# Start the server
./run.sh
```

The server will start at `http://localhost:8001`

**Alternative**: Run directly with uvicorn
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 4. Verify Installation

Open another terminal and test:

```bash
# Test health endpoint
curl http://localhost:8001/health

# Should return:
# {"status":"healthy","gemini_api":true,"database":true,"memory_sessions":0}
```

Or visit in browser: http://localhost:8001/docs

---

## SillyTavern Configuration

### Method 1: Using SillyTavern UI (Recommended)

1. **Open SillyTavern** at `http://localhost:8000` (SillyTavern's own server)
2. Click the **hamburger menu** (☰) in the top-left → **API Connections**
3. Select **API**: `Chat Completion`
4. Select **Chat Completion Source**: `Custom (OpenAI-compatible)`
5. **Configure the connection**:
   - **API URL**: `http://localhost:8001/v1` (note: port 8001, not 8000)
   - **API Key**: `sk-anything` (put any dummy key, it's not validated)
   - **Model**: `gemini-2.0-flash-exp` (or whatever model you set in `.env`)
6. Click the **Test** button - should show a green checkmark ✓
7. Click **Connect**

**Important**: 
- SillyTavern runs on port **8000**
- Your backend runs on port **8001** 
- Make sure to use `http://localhost:8001/v1` in the API URL setting

### Method 2: Manual Configuration

Edit SillyTavern's `config.yaml`:

```yaml
api_type: openai
api_url: http://localhost:8001/v1
api_key: ""
model: gemini-2.0-flash-exp
```

---

## Testing the System

### Test 1: Basic Chat

```bash
cd examples
python test_usage.py
```

This will run comprehensive tests including:
- Basic chat completion
- Multi-turn conversation
- Streaming responses
- Memory retrieval

### Test 2: Manual Test

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.0-flash-exp",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "user": "test_chat"
  }'
```

### Test 3: In SillyTavern

1. Load a character card
2. Start chatting normally
3. After 20+ messages, the system will automatically:
   - Summarize old messages
   - Retrieve relevant context
   - Never forget the persona

---

## Verification Checklist

✅ Server starts without errors  
✅ Health endpoint returns "healthy"  
✅ SillyTavern connection test succeeds  
✅ First message generates response  
✅ Character details are remembered  
✅ Session data saved to `data/sessions/`  

---

## Common Issues

### Issue: Import errors when starting

**Solution**: Make sure you're in the virtual environment
```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

### Issue: "Gemini API connection failed"

**Solutions**:
1. Check your API key in `.env`
2. Verify API key is active at https://makersuite.google.com/
3. Check internet connection
4. Make sure you have the latest `google-genai` SDK installed: `pip install -U google-genai`

### Issue: SillyTavern can't connect

**Solutions**:
1. Verify backend is running: `curl http://localhost:8001/health`
2. Make sure SillyTavern is using the correct URL: `http://localhost:8001/v1` (port **8001**, not 8000)
3. Check firewall isn't blocking port 8001
4. If running on different machine, change `HOST` in `.env` to `0.0.0.0`
5. Ensure both SillyTavern and your backend are running (SillyTavern on port 8000, backend on port 8001)

### Issue: Port conflict

**Solution**: If you get "address already in use" error:
1. SillyTavern uses port 8000 by default
2. This backend uses port 8001 to avoid conflicts
3. You can change the backend port in `.env` by setting `PORT=8002` (or any other free port)
4. Remember to update the API URL in SillyTavern to match!

### Issue: Slow responses

**Solutions**:
1. Reduce `RAG_TOP_K` in `.env` (try 1 or 2)
2. Reduce `MAX_WORKING_MEMORY_SIZE` to 10
3. Use `gemini-1.5-flash` instead of `gemini-1.5-pro`

### Issue: High memory usage

**Solution**: Embeddings are cached in RAM. Restart periodically or:
```python
# In .env, reduce:
MAX_WORKING_MEMORY_SIZE=10
```

---

## Next Steps

### Optimize for Your Use Case

**For RP/Creative Writing**:
```env
TEMPERATURE=0.9
RAG_TOP_K=3
SYSTEM_TOKEN_PERCENT=25  # More persona context
GEMINI_MODEL=gemini-2.0-flash-exp  # Fast and creative
```

**For Informational/Tutoring**:
```env
TEMPERATURE=0.5
RAG_TOP_K=5
RAG_TOKEN_PERCENT=30  # More retrieved context
GEMINI_MODEL=gemini-2.0-flash-exp
```

### Enable Advanced Features (Phase 2)

Coming soon:
- ChromaDB for persistent embeddings
- Cross-encoder reranking
- Transformer-based emotion detection
- Redis for distributed sessions

---

## Data Management

### View Session Data

```bash
# List all sessions
ls data/sessions/

# Query a session database
sqlite3 data/sessions/<chat_id>.db

sqlite> SELECT COUNT(*) FROM messages;
sqlite> SELECT * FROM messages ORDER BY timestamp DESC LIMIT 5;
sqlite> SELECT * FROM personas;
```

### Backup Sessions

```bash
# Backup all session data
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

### Clear Old Sessions

```bash
# Remove sessions older than 30 days
find data/sessions/ -name "*.db" -mtime +30 -delete
```

---

## Performance Tips

1. **Use SSD** for `data/sessions/` directory
2. **Adjust token budgets** based on your needs
3. **Monitor logs** in `logs/app.log`
4. **Track costs** via `/health` endpoint
5. **Summarize frequently** for long conversations (set `SUMMARIZE_AFTER_MESSAGES=15`)

---

## Getting Help

- **Documentation**: See main `README.md`
- **Logs**: Check `logs/app.log` for errors
- **API Docs**: Visit `http://localhost:8001/docs`
- **Health Check**: `curl http://localhost:8001/health`
- **Issues**: Open a GitHub issue with logs

---

## Success Indicators

You'll know it's working when:

✨ Character never forgets core personality  
✨ References past conversations accurately  
✨ Adapts to emotional context  
✨ Responses stay consistent after 100+ messages  
✨ No "I don't recall" or persona drift  

---

**Enjoy your production-ready emotional RAG backend!** 🚀
