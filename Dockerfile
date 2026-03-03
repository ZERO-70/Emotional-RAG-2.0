# ============================================================
# Emotional RAG Backend - Docker Image
# Multi-stage, CPU-only build for lightweight deployment
# ============================================================

# ----- Stage 1: Builder -----
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (saves ~1.5GB vs GPU version)
RUN pip install --no-cache-dir --target=/deps \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --target=/deps -r requirements-docker.txt

# ----- Stage 2: Runtime -----
FROM python:3.12-slim

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages

# Copy application code
COPY app/ /app/app/
COPY start.sh /app/start.sh
COPY .env.example /app/.env.example

# Create data and log directories
RUN mkdir -p /app/data/sessions /app/data/embeddings /app/data/chromadb /app/logs /app/knowledge_base/chats /app/knowledge_base/docs

# Pre-download all ML models at build time so the container
# works fully offline with no internet needed on first startup.
#
# Model sizes (added to image):
#   all-MiniLM-L6-v2                         ~90 MB  (embeddings)
#   cross-encoder/ms-marco-MiniLM-L6-v2      ~85 MB  (reranker)
#   j-hartmann/emotion-english-distilroberta  ~330 MB (emotion detection)
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
from transformers import pipeline; \
print('Downloading embedding model...'); \
m1 = SentenceTransformer('all-MiniLM-L6-v2'); \
print(f'  all-MiniLM-L6-v2: dim={m1.get_sentence_embedding_dimension()}'); \
print('Downloading reranker model...'); \
m2 = CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2'); \
print('  cross-encoder/ms-marco-MiniLM-L6-v2: OK'); \
print('Downloading emotion detection model...'); \
m3 = pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base'); \
print('  j-hartmann/emotion-english-distilroberta-base: OK'); \
print('All models downloaded successfully.')"

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Declare volumes (these get bind-mounted at runtime from the host)
VOLUME ["/app/data", "/app/knowledge_base"]

# Run (no --reload in production)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
