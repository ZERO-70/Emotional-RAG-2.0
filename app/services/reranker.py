"""Cross-encoder reranking for improved retrieval accuracy.

Phase 2 enhancement providing:
- Two-stage retrieval (bi-encoder → cross-encoder)
- More accurate relevance scoring
- Better precision for top results
"""

import logging
from typing import List, Tuple, Dict, Any

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder reranking for two-stage retrieval.
    
    Workflow:
    1. Bi-encoder retrieves top 50 candidates (fast, approximate)
    2. Cross-encoder reranks to top 10 (slow, accurate)
    
    Benefits:
    - Higher precision than bi-encoder alone
    - Considers full query-document interaction
    - Better semantic understanding
    """
    
    def __init__(self, model_name: str = None):
        """Initialize cross-encoder model.
        
        Args:
            model_name: HuggingFace model name (default from settings)
        """
        if not CROSS_ENCODER_AVAILABLE:
            raise ImportError(
                "sentence-transformers cross-encoder not available. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name or settings.reranker_model
        logger.info(f"Loading cross-encoder model: {self.model_name}")
        
        try:
            self.model = CrossEncoder(self.model_name)
            logger.info("Cross-encoder loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}", exc_info=True)
            raise
    
    def rerank(
        self,
        query: str,
        candidates: List[Tuple[str, str, Dict[str, Any], float]],
        top_k: int = None
    ) -> List[Tuple[str, str, Dict[str, Any], float]]:
        """Rerank candidates using cross-encoder.
        
        Args:
            query: Query text
            candidates: List of (id, text, metadata, bi_encoder_score)
            top_k: Number of top results to return (default from settings)
            
        Returns:
            Reranked candidates with new scores
        """
        if not candidates:
            return []
        
        top_k = top_k or settings.reranking_top_k
        
        # Prepare query-document pairs
        pairs = [(query, candidate[1]) for candidate in candidates]
        
        try:
            # Get cross-encoder scores
            scores = self.model.predict(pairs)
            
            # Combine with candidates and sort
            reranked = [
                (
                    candidates[i][0],  # id
                    candidates[i][1],  # text
                    candidates[i][2],  # metadata
                    float(scores[i])   # cross-encoder score
                )
                for i in range(len(candidates))
            ]
            
            # Sort by cross-encoder score (descending)
            reranked.sort(key=lambda x: x[3], reverse=True)
            
            logger.debug(
                "Reranking completed",
                extra={
                    "candidates": len(candidates),
                    "returned": min(top_k, len(reranked))
                }
            )
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # Fallback: return original candidates
            return candidates[:top_k]
