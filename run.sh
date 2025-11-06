#!/bin/bash

# Emotional RAG Backend Startup Script

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Emotional RAG Backend...${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env and add your GEMINI_API_KEY before continuing.${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Create data directories
mkdir -p data/sessions
mkdir -p data/embeddings

# Download embedding model (if not cached)
echo -e "${GREEN}Checking embedding model...${NC}"
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" 2>/dev/null || echo -e "${YELLOW}Downloading embedding model on first run...${NC}"

# Start the server
echo -e "${GREEN}Starting FastAPI server...${NC}"
echo -e "${GREEN}Access at: http://localhost:8001${NC}"
echo -e "${GREEN}API Docs: http://localhost:8001/docs${NC}"
echo -e "${GREEN}Health Check: http://localhost:8001/health${NC}"

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
