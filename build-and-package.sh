#!/usr/bin/env bash
# ============================================================
# build-and-package.sh
# One-shot script to:
#   1. Build the emotional-rag Docker image
#   2. Pull sidecar images
#   3. Export all images to a single .tar.gz archive
#   4. Assemble the client-package directory
#   5. Zip the final deliverable
# ============================================================
# Usage:
#   chmod +x build-and-package.sh
#   ./build-and-package.sh
#
# Output:
#   emotional-rag-client.zip   (~4-6 GB, ready to send)
# ============================================================

set -e   # exit on any error

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_DIR="$PROJECT_ROOT/client-package"
ARCHIVE_NAME="emotional-rag-images.tar.gz"
OUTPUT_ZIP="emotional-rag-client.zip"

echo ""
echo "======================================================="
echo "  Emotional RAG — Docker Build & Package Script"
echo "======================================================="
echo ""

# ── Step 1: Build the main image ─────────────────────────────
echo "[1/5] Building emotional-rag:latest ..."
echo "      (This takes 15–30 min on first build — models are downloaded)"
echo ""
cd "$PROJECT_ROOT"
docker build -t emotional-rag:latest .
echo ""
echo "  ✓ emotional-rag:latest built successfully"
echo ""

# ── Step 2: Pull sidecar images ──────────────────────────────
echo "[2/5] Pulling sidecar images ..."
docker pull chromadb/chroma:latest
echo "  ✓ chromadb/chroma:latest"
echo ""

# ── Step 3: Export to tar.gz ─────────────────────────────────
echo "[3/5] Exporting all images to $ARCHIVE_NAME ..."
echo "      (Estimating 4–6 GB, may take a few minutes)"
echo ""

# Use pv for progress if available, otherwise plain pipe
if command -v pv &> /dev/null; then
    docker save \
        emotional-rag:latest \
        chromadb/chroma:latest \
    | pv | gzip > "$CLIENT_DIR/$ARCHIVE_NAME"
else
    docker save \
        emotional-rag:latest \
        chromadb/chroma:latest \
    | gzip > "$CLIENT_DIR/$ARCHIVE_NAME"
fi

echo "  ✓ Archive saved: client-package/$ARCHIVE_NAME"
echo ""

# ── Step 4: Assemble client package ──────────────────────────
echo "[4/5] Assembling client package ..."

# Compose file
cp "$PROJECT_ROOT/docker-compose.client.yml" "$CLIENT_DIR/docker-compose.client.yml"

# Env template (NOT the real .env with keys!)
cp "$PROJECT_ROOT/.env.example" "$CLIENT_DIR/.env.example"

# SQL schema
mkdir -p "$CLIENT_DIR/sql"
cp "$PROJECT_ROOT/sql/init.sql" "$CLIENT_DIR/sql/init.sql" 2>/dev/null || echo "  (no init.sql found, skipping)"

# Knowledge base (persona + docs)
echo "  Copying knowledge_base/ ..."
mkdir -p "$CLIENT_DIR/knowledge_base"
rsync -a --exclude='*.tmp' --exclude='.DS_Store' \
    "$PROJECT_ROOT/knowledge_base/" "$CLIENT_DIR/knowledge_base/"

# Required runtime directories (pre-create so volumes mount cleanly)
mkdir -p "$CLIENT_DIR/data/sessions"
mkdir -p "$CLIENT_DIR/data/chromadb"
mkdir -p "$CLIENT_DIR/data/embeddings"
mkdir -p "$CLIENT_DIR/logs"

echo "  ✓ Client package assembled"
echo ""

# ── Step 5: Zip the package ───────────────────────────────────
echo "[5/5] Creating final zip: $OUTPUT_ZIP ..."
cd "$PROJECT_ROOT"
zip -r "$OUTPUT_ZIP" client-package/
echo ""
echo "  ✓ Done! Output: $PROJECT_ROOT/$OUTPUT_ZIP"
echo ""

# ── Summary ──────────────────────────────────────────────────
ZIPSIZE=$(du -sh "$OUTPUT_ZIP" | cut -f1)
echo "======================================================="
echo "  Package ready: $OUTPUT_ZIP ($ZIPSIZE)"
echo ""
echo "  Send this file to the client and have them:"
echo "    1. Install Docker Desktop for Windows"
echo "    2. Extract the zip"
echo "    3. Double-click start-windows.bat"
echo "======================================================="
echo ""
