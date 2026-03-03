"""Knowledge Base Ingestion Service.

Ingests client-provided knowledge into ChromaDB:
- knowledge_base/chats/  → ChatGPT export JSONs
- knowledge_base/docs/   → Plain .txt files

Features:
- Manifest-based deduplication (only ingest new/changed files)
- Watchdog file watcher (auto-detect new files while running)
- Q+A pair chunking with 400-token soft cap
- Paragraph chunking for .txt docs
"""

import os
import json
import hashlib
import logging
import threading
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from app.core.config import settings

import numpy as np

logger = logging.getLogger(__name__)

MANIFEST_PATH = "./data/ingestion_manifest.json"
KNOWLEDGE_COLLECTION = "knowledge_base"
MAX_TOKENS_PER_CHUNK = 400   # all-MiniLM-L6-v2 hard limit is 256 tokens, we use 400 words ≈ safe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5(path: str) -> str:
    """Compute MD5 hash of a file for change detection."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _reset_manifest() -> None:
    """Delete the manifest file so the next ingest treats all files as new."""
    if os.path.exists(MANIFEST_PATH):
        try:
            os.remove(MANIFEST_PATH)
            logger.info("Ingestion manifest reset — all knowledge base files will be re-ingested.")
        except Exception as e:
            logger.warning(f"Could not delete manifest: {e}")


def _load_manifest() -> Dict[str, str]:
    """Load ingestion manifest {relative_path: md5_hash}."""
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load manifest: {e} — starting fresh")
    return {}


def _save_manifest(manifest: Dict[str, str]) -> None:
    """Persist manifest to disk."""
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def _word_count(text: str) -> int:
    return len(text.split())


def _chunk_text(text: str, max_words: int = MAX_TOKENS_PER_CHUNK) -> List[str]:
    """Split text into chunks of at most max_words words, by paragraph."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for para in paragraphs:
        para_words = _word_count(para)
        if current_words + para_words > max_words and current:
            chunks.append("\n\n".join(current))
            current = []
            current_words = 0
        current.append(para)
        current_words += para_words

    if current:
        chunks.append("\n\n".join(current))

    # If a single paragraph is still too long, hard-split by words
    result: List[str] = []
    for chunk in chunks:
        words = chunk.split()
        if len(words) <= max_words:
            result.append(chunk)
        else:
            for i in range(0, len(words), max_words):
                result.append(" ".join(words[i:i + max_words]))

    return result if result else [text[:2000]]


# ---------------------------------------------------------------------------
# Chat JSON parsing
# ---------------------------------------------------------------------------

def parse_chat_file(path: str) -> List[Dict]:
    """Parse a ChatGPT export JSON into a list of chunk dicts.

    Returns list of:
        {text, metadata: {source, title, filename, chunk_index, role}}
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    title = metadata.get("title", Path(path).stem)
    filename = Path(path).name
    messages = data.get("messages", [])

    chunks: List[Dict] = []
    chunk_index = 0

    # Pair up Prompt + Response
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "")
        text = msg.get("say", "").strip()

        if role == "Prompt" and text:
            question = text
            response = ""

            # Look ahead for the matching Response
            if i + 1 < len(messages) and messages[i + 1].get("role") == "Response":
                response = messages[i + 1].get("say", "").strip()
                i += 2
            else:
                i += 1

            # Build combined Q+A text
            combined = f"Q: {question}\n\nA: {response}" if response else f"Q: {question}"

            # Split into sub-chunks if too long
            sub_chunks = _chunk_text(combined)
            for sub_idx, sub_chunk in enumerate(sub_chunks):
                # For sub-chunks, prefix with the question for context
                if sub_idx > 0:
                    prefix = f"Q: {question[:200]}...\n\n" if len(question) > 200 else f"Q: {question}\n\n"
                    sub_chunk = prefix + sub_chunk

                chunks.append({
                    "text": sub_chunk,
                    "metadata": {
                        "source_type": "chat",
                        "filename": filename,
                        "title": title,
                        "chunk_index": chunk_index,
                        "role": "qa_pair"
                    }
                })
                chunk_index += 1
        else:
            i += 1

    return chunks


# ---------------------------------------------------------------------------
# Doc .txt parsing
# ---------------------------------------------------------------------------

def parse_doc_file(path: str) -> List[Dict]:
    """Parse a plain .txt file into paragraph chunks."""
    filename = Path(path).name
    title = Path(path).stem

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read().strip()

    sub_chunks = _chunk_text(content)
    chunks: List[Dict] = []
    for idx, chunk in enumerate(sub_chunks):
        chunks.append({
            "text": chunk,
            "metadata": {
                "source_type": "doc",
                "filename": filename,
                "title": title,
                "chunk_index": idx,
                "role": "document"
            }
        })
    return chunks


# ---------------------------------------------------------------------------
# KnowledgeIngester
# ---------------------------------------------------------------------------

class KnowledgeIngester:
    """Ingests knowledge_base/ files into ChromaDB `knowledge_base` collection."""

    def __init__(self, rag_engine, chromadb_store):
        """
        Args:
            rag_engine: RAGEngine instance (provides encode())
            chromadb_store: ChromaDBVectorStore instance
        """
        self.rag_engine = rag_engine
        self.chromadb_store = chromadb_store
        self._watcher_thread: Optional[threading.Thread] = None
        self._observer = None

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def _get_kb_collection(self):
        """Get or create the knowledge_base ChromaDB collection."""
        return self.chromadb_store.client.get_or_create_collection(
            name=KNOWLEDGE_COLLECTION,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:M": 16
            }
        )

    # ------------------------------------------------------------------
    # Ingestion helpers
    # ------------------------------------------------------------------

    def _embed_and_upsert(self, chunks: List[Dict], id_prefix: str) -> int:
        """Embed chunks and upsert into knowledge_base collection."""
        if not chunks:
            return 0

        collection = self._get_kb_collection()
        texts = [c["text"] for c in chunks]

        # Embed in batch using encode_batch (takes List[str], returns ndarray)
        embeddings = self.rag_engine.encode_batch(texts)  # shape: (N, dim)

        ids = [f"{id_prefix}_{i}" for i in range(len(chunks))]
        emb_lists = [e.tolist() for e in embeddings]
        metadatas = [c["metadata"] for c in chunks]

        collection.upsert(
            embeddings=emb_lists,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        return len(chunks)

    def _file_id_prefix(self, filepath: str, kb_root: str) -> str:
        """Generate a stable, filesystem-safe ID prefix for a file."""
        rel = os.path.relpath(filepath, kb_root)
        return "kb_" + hashlib.md5(rel.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_file(self, filepath: str, kb_root: str, manifest: Dict[str, str]) -> bool:
        """Ingest a single file. Returns True if ingested (new/changed)."""
        rel_path = os.path.relpath(filepath, kb_root)
        file_hash = _md5(filepath)

        if manifest.get(rel_path) == file_hash:
            logger.debug(f"Skipping unchanged file: {rel_path}")
            return False

        ext = Path(filepath).suffix.lower()
        try:
            if ext == ".json":
                chunks = parse_chat_file(filepath)
            elif ext == ".txt":
                chunks = parse_doc_file(filepath)
            else:
                logger.debug(f"Skipping unsupported file type: {rel_path}")
                return False

            id_prefix = self._file_id_prefix(filepath, kb_root)
            count = self._embed_and_upsert(chunks, id_prefix)
            manifest[rel_path] = file_hash
            logger.info(f"Ingested {rel_path}: {count} chunks")
            return True

        except Exception as e:
            logger.error(f"Failed to ingest {rel_path}: {e}", exc_info=True)
            return False

    def run_ingestion(self, kb_path: str) -> Dict[str, int]:
        """Scan knowledge_base/ and ingest new/changed files.

        Returns:
            {"files_ingested": N, "files_skipped": M, "total_chunks": K}
        """
        kb_path = os.path.abspath(kb_path)
        if not os.path.isdir(kb_path):
            logger.warning(f"knowledge_base not found at {kb_path} — skipping ingestion")
            return {"files_ingested": 0, "files_skipped": 0, "total_chunks": 0}

        # If configured to reset on start, wipe the manifest so every file
        # is treated as new and fully re-ingested into ChromaDB.
        if settings.reset_ingestion_on_start:
            _reset_manifest()

        manifest = _load_manifest()
        ingested = skipped = 0

        for root, _, files in os.walk(kb_path):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                if Path(fname).suffix.lower() in (".json", ".txt"):
                    if self.ingest_file(fpath, kb_path, manifest):
                        ingested += 1
                    else:
                        skipped += 1

        _save_manifest(manifest)

        total = self._get_kb_collection().count()
        logger.info(
            f"Knowledge base ingestion complete",
            extra={"files_ingested": ingested, "files_skipped": skipped, "total_embeddings": total}
        )
        return {"files_ingested": ingested, "files_skipped": skipped, "total_chunks": total}

    # ------------------------------------------------------------------
    # File watcher
    # ------------------------------------------------------------------

    def start_watcher(self, kb_path: str) -> None:
        """Start a background watchdog observer for the knowledge_base folder."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            kb_path = os.path.abspath(kb_path)
            ingester = self

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        self._handle(event.src_path)

                def on_modified(self, event):
                    if not event.is_directory:
                        self._handle(event.src_path)

                def _handle(self, fpath: str):
                    ext = Path(fpath).suffix.lower()
                    if ext in (".json", ".txt"):
                        logger.info(f"Detected file change: {fpath}")
                        manifest = _load_manifest()
                        if ingester.ingest_file(fpath, kb_path, manifest):
                            _save_manifest(manifest)

            self._observer = Observer()
            self._observer.schedule(_Handler(), kb_path, recursive=True)
            self._observer.start()
            logger.info(f"Knowledge base file watcher started on: {kb_path}")

        except ImportError:
            logger.warning("watchdog not installed — file watcher disabled. Install with: pip install watchdog")
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}", exc_info=True)

    def stop_watcher(self) -> None:
        """Stop the background file watcher."""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            logger.info("Knowledge base file watcher stopped")

    # ------------------------------------------------------------------
    # RAG search
    # ------------------------------------------------------------------

    async def search(self, query_embedding: np.ndarray, top_k: int = 5):
        """Search the knowledge_base collection.

        Returns:
            List of (id, document, metadata, distance)
        """
        try:
            collection = self._get_kb_collection()
            if collection.count() == 0:
                return []

            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(top_k, collection.count())
            )
            if not results["ids"] or not results["ids"][0]:
                return []

            return [
                (results["ids"][0][i],
                 results["documents"][0][i],
                 results["metadatas"][0][i],
                 results["distances"][0][i])
                for i in range(len(results["ids"][0]))
            ]
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}", exc_info=True)
            return []
