"""ChromaDB vector store for persistent embeddings storage.

Phase 2 enhancement providing:
- Persistent vector indices (no rebuild on startup)
- HNSW indexing for fast similarity search  
- Scalable to 100k+ embeddings
- Multi-session isolation via collections
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChromaDBVectorStore:
    """ChromaDB-based vector storage with persistent HNSW indices.
    
    Benefits over SQLite BLOB storage:
    - Persistent indices (faster startup)
    - HNSW algorithm for approximate nearest neighbors
    - Better scalability for large embedding collections
    - Native vector operations
    """
    
    def __init__(self):
        """Initialize ChromaDB client with persistence."""
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb not installed. Install with: pip install chromadb>=1.3.0"
            )
        
        # Client-server mode if host/port configured, otherwise persistent
        if settings.chromadb_host and settings.chromadb_port:
            logger.info(
                "Connecting to ChromaDB server",
                extra={
                    "host": settings.chromadb_host,
                    "port": settings.chromadb_port
                }
            )
            self.client = chromadb.HttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port
            )
        else:
            logger.info(
                "Using persistent ChromaDB",
                extra={"path": settings.chromadb_path}
            )
            self.client = chromadb.PersistentClient(
                path=settings.chromadb_path,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=False
                )
            )
        
        self._collections: Dict[str, Any] = {}
        logger.info("ChromaDB vector store initialized")
    
    def get_collection(self, chat_id: str) -> Any:
        """Get or create collection for a chat session.
        
        Args:
            chat_id: Unique chat identifier
            
        Returns:
            ChromaDB collection instance
        """
        if chat_id not in self._collections:
            # Sanitize collection name (alphanumeric + underscores only)
            collection_name = f"chat_{chat_id}".replace("-", "_")
            
            try:
                self._collections[chat_id] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",  # Use cosine distance
                        "hnsw:construction_ef": 100,  # Higher = better recall, slower build
                        "hnsw:M": 16  # Max connections per layer
                    }
                )
                logger.debug(
                    "Retrieved ChromaDB collection",
                    extra={"chat_id": chat_id, "collection": collection_name}
                )
            except Exception as e:
                logger.error(
                    f"Failed to get collection: {e}",
                    extra={"chat_id": chat_id},
                    exc_info=True
                )
                raise
        
        return self._collections[chat_id]
    
    async def add_embeddings(
        self,
        chat_id: str,
        embeddings: List[np.ndarray],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """Add embeddings to ChromaDB collection.
        
        Args:
            chat_id: Chat session identifier
            embeddings: List of embedding vectors
            documents: Corresponding text documents
            metadatas: Metadata dictionaries
            ids: Unique IDs for each embedding
        """
        collection = self.get_collection(chat_id)
        
        # Convert numpy arrays to lists for ChromaDB
        embedding_lists = [emb.tolist() for emb in embeddings]
        
        try:
            collection.add(
                embeddings=embedding_lists,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.debug(
                "Added embeddings to ChromaDB",
                extra={
                    "chat_id": chat_id,
                    "count": len(embeddings)
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to add embeddings: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            raise
    
    async def search_embeddings(
        self,
        chat_id: str,
        query_embedding: np.ndarray,
        top_k: int = 10,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, str, Dict[str, Any], float]]:
        """Search for similar embeddings using HNSW index.
        
        Args:
            chat_id: Chat session identifier
            query_embedding: Query vector
            top_k: Number of results to return
            where_filter: Optional metadata filter
            
        Returns:
            List of tuples: (id, document, metadata, distance)
        """
        collection = self.get_collection(chat_id)
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                where=where_filter
            )
            
            # Unpack results
            if not results['ids'] or not results['ids'][0]:
                return []
            
            output = []
            for i in range(len(results['ids'][0])):
                output.append((
                    results['ids'][0][i],
                    results['documents'][0][i],
                    results['metadatas'][0][i],
                    results['distances'][0][i]
                ))
            
            logger.debug(
                "ChromaDB search completed",
                extra={
                    "chat_id": chat_id,
                    "results": len(output)
                }
            )
            
            return output
            
        except Exception as e:
            logger.error(
                f"ChromaDB search failed: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            raise
    
    async def delete_collection(self, chat_id: str) -> None:
        """Delete a chat session's collection.
        
        Args:
            chat_id: Chat session identifier
        """
        collection_name = f"chat_{chat_id}".replace("-", "_")
        
        try:
            self.client.delete_collection(name=collection_name)
            if chat_id in self._collections:
                del self._collections[chat_id]
            
            logger.info(
                "Deleted ChromaDB collection",
                extra={"chat_id": chat_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to delete collection: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            raise
    
    async def get_collection_stats(self, chat_id: str) -> Dict[str, Any]:
        """Get statistics for a collection.
        
        Args:
            chat_id: Chat session identifier
            
        Returns:
            Dictionary with collection statistics
        """
        collection = self.get_collection(chat_id)
        
        try:
            count = collection.count()
            return {
                "chat_id": chat_id,
                "embedding_count": count,
                "backend": "chromadb"
            }
        except Exception as e:
            logger.error(
                f"Failed to get collection stats: {e}",
                extra={"chat_id": chat_id},
                exc_info=True
            )
            return {
                "chat_id": chat_id,
                "embedding_count": 0,
                "error": str(e)
            }
    
    async def close(self) -> None:
        """Clean up ChromaDB resources."""
        self._collections.clear()
        logger.info("ChromaDB vector store closed")
