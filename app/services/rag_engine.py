"""Semantic retrieval engine using sentence-transformers."""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
from app.models.memory import RAGResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGEngine:
    """Semantic retrieval using sentence-transformers embeddings."""
    
    def __init__(self):
        """Initialize RAG engine with embedding model."""
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        try:
            self.model = SentenceTransformer(settings.embedding_model)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded (dimension: {self.embedding_dim})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def encode(self, text: str) -> np.ndarray:
        """
        Encode text into embedding vector.
        
        Args:
            text: Input text to encode
            
        Returns:
            Numpy array of shape (embedding_dim,)
        """
        try:
            embedding = self.model.encode([text], convert_to_numpy=True)[0]
            return embedding
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            raise
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        Encode multiple texts in batch.
        
        Args:
            texts: List of texts to encode
            
        Returns:
            Numpy array of shape (n_texts, embedding_dim)
        """
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Batch encoding failed: {e}")
            raise
    
    def cosine_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1 (typically 0-1 for similar texts)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Compute cosine similarity
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
        """
        Search for most similar embeddings.
        
        Args:
            query_embedding: Query vector
            candidate_embeddings: List of (embedding, metadata) tuples
            top_k: Number of top results to return
            emotional_boost: Whether to boost emotionally similar results
            query_emotion: Current query emotion for boosting
            
        Returns:
            List of RAGResult objects sorted by relevance
        """
        if not candidate_embeddings:
            return []
        
        scores = []
        for embedding, metadata in candidate_embeddings:
            # Calculate base semantic similarity
            similarity = self.cosine_similarity(query_embedding, embedding)
            
            # Apply emotional boost if enabled
            if emotional_boost and query_emotion and metadata.get('emotion'):
                message_emotion = metadata.get('emotion')
                importance = metadata.get('importance_score', 0.5)
                
                # Boost if emotions match
                if message_emotion == query_emotion and message_emotion != 'neutral':
                    emotional_boost_factor = 1 + (importance * 0.3)
                    similarity *= emotional_boost_factor
                    metadata['emotional_boost'] = emotional_boost_factor
            
            scores.append((similarity, metadata))
        
        # Sort by score (descending)
        scores.sort(reverse=True, key=lambda x: x[0])
        
        # Return top-k results
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
        """
        Split text into overlapping chunks for embedding.
        
        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near chunk boundary
                for punct in ['. ', '! ', '? ', '\n\n']:
                    punct_pos = text.rfind(punct, start, end)
                    if punct_pos > start + chunk_size // 2:
                        end = punct_pos + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap
        
        logger.debug(f"Chunked text into {len(chunks)} segments")
        return chunks
    
    def format_results_for_context(
        self,
        results: List[RAGResult],
        max_tokens: int
    ) -> str:
        """
        Format RAG results into context string with token limit.
        
        Args:
            results: Retrieved RAG results
            max_tokens: Maximum tokens allowed
            
        Returns:
            Formatted context string
        """
        if not results:
            return ""
        
        context_parts = []
        total_chars = 0
        # Rough estimate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        
        for result in results:
            source_label = {
                'persona': '📋 Character Detail',
                'message': '💬 Past Conversation',
                'summary': '📝 Earlier Summary'
            }.get(result.source, '📌 Relevant Context')
            
            formatted = f"{source_label} (relevance: {result.relevance_score:.2f}):\n{result.text}\n"
            
            if total_chars + len(formatted) > max_chars:
                # Try to fit partial text
                remaining = max_chars - total_chars
                if remaining > 100:  # Only add if meaningful space left
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
        """Convert numpy embedding to bytes for SQLite storage."""
        return embedding.astype(np.float32).tobytes()
    
    def bytes_to_embedding(self, data: bytes) -> np.ndarray:
        """Convert bytes back to numpy embedding."""
        return np.frombuffer(data, dtype=np.float32)
