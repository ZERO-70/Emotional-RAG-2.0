"""Semantic retrieval engine using OpenAI embeddings."""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from app.models.memory import RAGResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGEngine:
    """Semantic retrieval using OpenAI embedding API."""

    def __init__(self):
        """Initialize RAG engine with OpenAI embedding client."""
        logger.info(f"Initializing OpenAI embedding model: {settings.embedding_model}")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self.embedding_dim = settings.embedding_dimensions
        logger.info(f"OpenAI embedding model ready (dimension: {self.embedding_dim})")

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(
            input=texts,
            model=self._model,
            dimensions=self.embedding_dim,
        )
        return [d.embedding for d in resp.data]

    def encode(self, text: str) -> np.ndarray:
        vecs = self._get_embeddings([text])
        return np.array(vecs[0], dtype=np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([], dtype=np.float32)
        vecs = self._get_embeddings(texts)
        return np.array(vecs, dtype=np.float32)

    def cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        return float(similarity)

    def search_embeddings(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[Tuple[np.ndarray, Dict]],
        top_k: int = 3,
        emotional_boost: bool = False,
        query_emotion: Optional[str] = None
    ) -> List[RAGResult]:
        if not candidate_embeddings:
            return []

        scores = []
        for embedding, metadata in candidate_embeddings:
            similarity = self.cosine_similarity(query_embedding, embedding)

            if emotional_boost and query_emotion and metadata.get('emotion'):
                message_emotion = metadata.get('emotion')
                importance = metadata.get('importance_score', 0.5)
                if message_emotion == query_emotion and message_emotion != 'neutral':
                    emotional_boost_factor = 1 + (importance * 0.3)
                    similarity *= emotional_boost_factor
                    metadata['emotional_boost'] = emotional_boost_factor

            scores.append((similarity, metadata))

        scores.sort(reverse=True, key=lambda x: x[0])

        results = []
        for score, metadata in scores[:top_k]:
            results.append(RAGResult(
                text=metadata.get('content', ''),
                source=metadata.get('source', 'unknown'),
                relevance_score=round(score, 4),
                emotional_boost=metadata.get('emotional_boost')
            ))

        logger.debug(
            f"RAG search returned {len(results)} results",
            extra={
                "top_k": top_k,
                "total_candidates": len(candidate_embeddings),
                "top_score": results[0].relevance_score if results else 0,
                "emotional_boost_enabled": emotional_boost
            }
        )

        return results

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 200,
        overlap: int = 50
    ) -> List[str]:
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end < len(text):
                for punct in ['. ', '! ', '? ', '\n\n']:
                    punct_pos = text.rfind(punct, start, end)
                    if punct_pos > start + chunk_size // 2:
                        end = punct_pos + len(punct)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        logger.debug(f"Chunked text into {len(chunks)} segments")
        return chunks

    def format_results_for_context(
        self,
        results: List[RAGResult],
        max_tokens: int
    ) -> str:
        if not results:
            return ""

        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4

        for result in results:
            source_label = {
                'persona': 'Character Detail',
                'message': 'Past Conversation',
                'summary': 'Earlier Summary'
            }.get(result.source, 'Relevant Context')

            formatted = f"{source_label} (relevance: {result.relevance_score:.2f}):\n{result.text}\n"

            if total_chars + len(formatted) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
                    truncated_text = result.text[:remaining - 50] + "..."
                    formatted = f"{source_label}:\n{truncated_text}\n"
                    context_parts.append(formatted)
                break

            context_parts.append(formatted)
            total_chars += len(formatted)

        if context_parts:
            header = "## Retrieved Context\nThe following information is relevant to the current conversation:\n\n"
            return header + "\n".join(context_parts)

        return ""

    def embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        return embedding.astype(np.float32).tobytes()

    def bytes_to_embedding(self, data: bytes) -> np.ndarray:
        return np.frombuffer(data, dtype=np.float32)
