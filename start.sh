#!/bin/bash

# Emotional RAG Backend - Quick Start Script

echo "🚀 Starting Emotional RAG Backend..."
echo ""

# Navigate to project root
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run: python3 -m venv venv"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Copy .env.example to .env and configure it."
    exit 1
fi

# Create data directories if they don't exist
mkdir -p data/sessions data/embeddings data/chromadb logs

echo "✅ Data directories ready"
echo ""
echo "📡 Starting server on http://localhost:8001"
echo "   API Docs: http://localhost:8001/docs"
echo "   Health: http://localhost:8001/health"
echo ""

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
