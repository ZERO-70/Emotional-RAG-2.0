# 🚀 Getting Started - First Time Setup

Welcome to the Emotional RAG Backend! This guide will get you up and running in **5 minutes**.

---

## 📋 Prerequisites

Before you start, make sure you have:

- ✅ **Python 3.10+** installed
- ✅ **Google Gemini API key** ([Get one free here](https://makersuite.google.com/app/apikey))
- ✅ **2GB free disk space**
- ✅ **Internet connection** (for downloading models)

---

## ⚡ Quick Setup (Automated)

### Option 1: Use the Setup Script (Recommended)

```bash
# Run the automated setup
python3 setup.py

# Follow the prompts - it will:
# ✅ Create virtual environment
# ✅ Install all dependencies
# ✅ Download embedding models
# ✅ Create data directories
# ✅ Set up .env file
```

After setup completes:

```bash
# Edit .env and add your Gemini API key
nano .env  # or vim, vscode, etc.

# Start the server
./run.sh
```

---

## 🔧 Manual Setup

If you prefer to do it step by step:

### Step 1: Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### Step 2: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all packages
pip install -r requirements.txt

# This will download ~800MB of dependencies including:
# - FastAPI & Uvicorn
# - Google Gemini SDK
# - Sentence-transformers model (~80MB)
# - SQLite support
```

### Step 3: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set your API key
# IMPORTANT: Replace 'your_api_key_here' with actual key
nano .env
```

**Minimum required configuration:**
```env
GEMINI_API_KEY=your_actual_api_key_here
```

### Step 4: Verify Installation

```bash
# Run verification script
python3 verify.py

# Should show all green checkmarks ✅
```

### Step 5: Start the Server

```bash
# Make run script executable
chmod +x run.sh

# Start the backend
./run.sh

# Alternative: Run directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## ✅ Verify It's Working

### Test 1: Health Check

```bash
curl http://localhost:8001/health
```

**Expected output:**
```json
{
  "status": "healthy",
  "gemini_api": true,
  "database": true,
  "memory_sessions": 0,
  "timestamp": "2025-11-04T..."
}
```

### Test 2: API Documentation

Open in browser: http://localhost:8001/docs

You should see the interactive Swagger UI.

### Test 3: Simple Chat

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.0-flash-exp",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

---

## 🎮 Configure SillyTavern

Now that the backend is running, connect it to SillyTavern:

### Step-by-Step:

1. **Open SillyTavern**

2. **Click the hamburger menu** (☰) in top left

3. **Go to "API Connections"**

4. **Select API type:**
   - Choose: **"Chat Completion"**

5. **Select source:**
   - Choose: **"Custom (OpenAI-compatible)"**

6. **Configure settings:**
   ```
   API URL: http://localhost:8001/v1
   API Key: (leave blank)
   Model:   gemini-2.0-flash-exp
   ```

7. **Test connection:**
   - Click the **"Test"** button
   - Should show **green checkmark** ✅

8. **Connect:**
   - Click **"Connect"**

9. **Done!** 🎉

### Test in SillyTavern:

1. Load any character card
2. Send a message
3. You should get a response!

---

## 🧪 Run Example Tests

```bash
cd examples
python test_usage.py
```

This will test:
- ✅ Basic chat completion
- ✅ Multi-turn conversation
- ✅ Streaming responses
- ✅ Memory retrieval

---

## 📊 Understanding the System

### What Happens When You Send a Message:

```
Your message in SillyTavern
         ↓
1. Emotion Detection
   "User is feeling happy"
         ↓
2. RAG Retrieval
   "Retrieved 3 relevant memories"
         ↓
3. Context Building
   "Built 2500-token context with persona"
         ↓
4. Gemini API Call
   "Generated response in 1.5s"
         ↓
5. Storage
   "Saved with embeddings"
         ↓
Response appears in SillyTavern
```

### Where Data is Stored:

```
data/
├── sessions/
│   └── {chat_id}.db    ← Your conversation history
└── embeddings/          ← Cached embeddings (Phase 2)

logs/
└── app.log             ← Application logs
```

---

## 🎯 Verify Core Features

### Feature 1: Persona Persistence

```
1. Create a detailed character in SillyTavern
2. Chat for 50+ messages
3. Ask: "What's your name?"
4. ✅ Should remember perfectly
```

### Feature 2: Semantic Memory

```
1. Chat: "I love chocolate ice cream"
2. Chat about other topics for 30 messages
3. Ask: "What's my favorite dessert?"
4. ✅ Should retrieve from memory
```

### Feature 3: Emotional Awareness

```
1. Send: "I'm feeling really sad today"
2. ✅ Response should be empathetic
3. Later ask: "How was I feeling earlier?"
4. ✅ Should remember emotional context
```

### Feature 4: Summarization

```
1. Chat for 20+ messages
2. Check logs/app.log
3. ✅ Should see "Triggered background summarization"
4. Old messages compressed but remembered
```

---

## 🔧 Customization

### Optimize for Creative Writing:

Edit `.env`:
```env
GEMINI_MODEL=gemini-2.0-flash-exp
TEMPERATURE=0.9
RAG_TOP_K=3
SYSTEM_TOKEN_PERCENT=25  # More space for persona
```

### Optimize for Speed:

Edit `.env`:
```env
GEMINI_MODEL=gemini-2.0-flash-exp  # Faster, cheaper
RAG_TOP_K=1
MAX_WORKING_MEMORY_SIZE=10
```

### Optimize for Long Conversations:

Edit `.env`:
```env
SUMMARIZE_AFTER_MESSAGES=15  # Summarize more often
RAG_TOKEN_PERCENT=30         # More retrieved context
```

---

## 🐛 Troubleshooting

### Issue: "Gemini API connection failed"

**Solution:**
```bash
# 1. Check your API key in .env
cat .env | grep GEMINI_API_KEY

# 2. Test API key manually
curl https://generativelanguage.googleapis.com/v1/models?key=YOUR_KEY

# 3. Verify key is active at:
# https://makersuite.google.com/app/apikey
```

### Issue: "Import errors when starting"

**Solution:**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Check if packages are installed
pip list | grep -E 'fastapi|google-generativeai|sentence'

# Reinstall if needed
pip install -r requirements.txt
```

### Issue: "SillyTavern can't connect"

**Solution:**
```bash
# 1. Verify backend is running
curl http://localhost:8001/health

# 2. Check if port 8000 is in use
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# 3. Try different port in .env
PORT=8001

# 4. Update SillyTavern URL accordingly
```

### Issue: "Slow responses"

**Solution:**
```bash
# In .env, try:
GEMINI_MODEL=gemini-2.0-flash-exp  # 2x faster
RAG_TOP_K=1                    # Less retrieval
MAX_WORKING_MEMORY_SIZE=10     # Less context
```

---

## 📚 Next Steps

Once you have it running:

1. **Read the full docs:**
   - `README.md` - Overview and features
   - `ARCHITECTURE.md` - How it works internally
   - `PROJECT_SUMMARY.md` - Complete feature list

2. **Explore the API:**
   - Visit http://localhost:8001/docs
   - Try different endpoints
   - Test streaming responses

3. **Monitor your sessions:**
   ```bash
   # View session databases
   ls data/sessions/
   
   # Query a session
   sqlite3 data/sessions/your_chat_id.db
   SELECT COUNT(*) FROM messages;
   ```

4. **Check the logs:**
   ```bash
   # Follow logs in real-time
   tail -f logs/app.log
   
   # Filter by level
   grep ERROR logs/app.log
   ```

5. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

---

## 🎓 Learning Resources

### Understanding RAG:
- The system uses **sentence-transformers** for embeddings
- Semantic search finds relevant past messages
- Combines with emotional importance scoring

### Understanding Memory Tiers:
- **Working Memory**: Last 20 messages (RAM)
- **Short-term**: Full history (SQLite)
- **Long-term**: Embeddings for search

### Understanding Token Management:
- 20% for persona (always included)
- 25% for RAG context
- 35% for history
- 20% for response

---

## 🤝 Getting Help

If you run into issues:

1. **Check the logs:**
   ```bash
   tail -50 logs/app.log
   ```

2. **Run verification:**
   ```bash
   python3 verify.py
   ```

3. **Check health endpoint:**
   ```bash
   curl http://localhost:8001/health
   ```

4. **Test Gemini API directly:**
   ```python
   import google.generativeai as genai
   genai.configure(api_key="YOUR_KEY")
   model = genai.GenerativeModel('gemini-2.0-flash-exp')
   response = model.generate_content("Hello")
   print(response.text)
   ```

---

## ✨ Success Indicators

You'll know everything is working when:

- ✅ Health check returns "healthy"
- ✅ SillyTavern connects successfully
- ✅ Character details are never forgotten
- ✅ Past conversations are remembered
- ✅ Emotional context is maintained
- ✅ Responses stay consistent after 100+ messages

---

## 🎉 You're Ready!

Your Emotional RAG Backend is now running and ready to enhance your SillyTavern experience with:

- 🧠 **Perfect memory** - Never forgets character details
- 🔍 **Semantic search** - Finds relevant past conversations
- ❤️ **Emotional awareness** - Responds to your feelings
- 📝 **Smart summarization** - Preserves important moments
- ⚡ **Fast responses** - Optimized context building

**Enjoy your enhanced roleplaying experience!** 🚀

---

**Need more details?** See `QUICKSTART.md` for advanced setup or `README.md` for full documentation.
