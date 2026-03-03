# Emotional RAG Backend — Client Setup Guide

## Prerequisites (one-time install)

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop/
   - During install, accept the WSL2 setup prompt (required)
   - Restart your PC if prompted

2. **Start Docker Desktop** — look for the whale icon in the system tray

---

## First-Time Setup

1. Extract the `emotional-rag-client.zip` to a folder, e.g.:
   ```
   C:\emotional-rag\
   ```

2. Double-click **`start-windows.bat`**

3. On first run, the script will:
   - Load all Docker images (~10–20 minutes — only once)
   - Create a `.env` file from the template
   - Tell you to add your API key

4. Open `.env` in Notepad and set your API key:
   ```
   # For OpenRouter (recommended free option):
   OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE

   # For Gemini:
   GEMINI_API_KEY=YOUR_KEY_HERE
   ```

5. Run **`start-windows.bat`** again — the app will start!

---

## Daily Use

| Action           | How                              |
| ---------------- | -------------------------------- |
| **Start**        | Double-click `start-windows.bat` |
| **Stop**         | Double-click `stop-windows.bat`  |
| **API Docs**     | http://localhost:8001/docs       |
| **Health check** | http://localhost:8001/health     |
| **API endpoint** | http://localhost:8001            |

---

## What is Running?

| Service                  | Purpose                         | Port          |
| ------------------------ | ------------------------------- | ------------- |
| `emotional-rag-api`      | Main FastAPI backend            | 8001          |
| `emotional-rag-chromadb` | Vector database (RAG retrieval) | internal only |

> **Note:** ChromaDB runs as a **separate** container — it is not part of the main API image. Its data is saved in a Docker-managed volume and persists across restarts.

---

## Your Data

All persistent data is stored in:
- `data/` — conversation sessions, SQLite DBs
- `chromadb-data` Docker volume — vector embeddings (auto-managed by Docker)
- `knowledge_base/` — your persona/document files (read-only, you can edit these)

Stopping the app does **not** delete any data.

---

## Troubleshooting

**"Docker Desktop is not running"**
→ Open Docker Desktop from the Start Menu and wait for it to fully load (whale icon turns solid).

**App won't start / health check fails**
→ Wait 60 seconds after starting — the ML models need time to initialize on first run of a fresh session.

**Port 8001 already in use**
→ Another app is using port 8001. Stop it, or contact your provider to use a different port.

**How to update the knowledge base**
→ Add/edit files in the `knowledge_base/` folder and restart the app.

---

## Contact

For support, contact the developer who provided this package.
