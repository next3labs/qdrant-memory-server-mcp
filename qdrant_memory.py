"""
Qdrant-based memory for OpenCode Forge.
Uses Qdrant Cloud for vector storage.
"""
import os
import uuid
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer


class QdrantMemory:
    """Vector memory stored in Qdrant."""
    
    def __init__(
        self,
        qdrant_url: str = None,
        qdrant_api_key: str = None,
        collection_name: str = "opencode_memory",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY", "")
        self.collection_name = collection_name
        
        # Initialize Qdrant client
        if self.qdrant_url:
            # Check if it's a cloud URL or local
            if "pinecone" in self.qdrant_url or self.qdrant_api_key:
                # Cloud mode
                self.client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key
                )
            else:
                # Local mode (Docker)
                self.client = QdrantClient(url=self.qdrant_url)
        else:
            # Local file mode
            self.client = QdrantClient(path="./.opencode/memory/qdrant")
        
        # Initialize embedding model
        print(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        print("Embedding model loaded")
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 output size
                    distance=Distance.COSINE
                )
            )
            print(f"Created collection: {self.collection_name}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        return self.model.encode(text).tolist()
    
    def add(
        self,
        content: str,
        memory_type: str = "context",
        tags: List[str] = None,
        source_agent: str = "unknown",
        source_file: str = None,
        **kwargs
    ) -> str:
        """Add a memory to the vector store."""
        memory_id = str(uuid.uuid4())
        embedding = self._get_embedding(content)
        
        point = PointStruct(
            id=memory_id,
            vector=embedding,
            payload={
                "content": content,
                "type": memory_type,
                "tags": tags or [],
                "source_agent": source_agent,
                "source_file": source_file,
                **kwargs
            }
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return memory_id
    
    def query(
        self,
        query: str,
        memory_type: str = None,
        tags: List[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity."""
        query_vector = self._get_embedding(query)
        
        # Build filter conditions
        must_conditions = []
        if memory_type:
            must_conditions.append(
                FieldCondition(key="type", match=MatchValue(value=memory_type))
            )
        if tags:
            for tag in tags:
                must_conditions.append(
                    FieldCondition(key="tags", match=MatchValue(value=tag))
                )
        
        filter_clause = Filter(must=must_conditions) if must_conditions else None
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=filter_clause,
            limit=limit
        )
        
        return [
            {
                "id": r.id,
                "content": r.payload.get("content"),
                "type": r.payload.get("type"),
                "tags": r.payload.get("tags", []),
                "source_agent": r.payload.get("source_agent"),
                "source_file": r.payload.get("source_file"),
                "score": r.score
            }
            for r in results
        ]
    
    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific memory by ID."""
        results = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[memory_id]
        )
        
        if results:
            r = results[0]
            return {
                "id": r.id,
                "content": r.payload.get("content"),
                "type": r.payload.get("type"),
                "tags": r.payload.get("tags", []),
                "source_agent": r.payload.get("source_agent"),
                "source_file": r.payload.get("source_file")
            }
        return None
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[memory_id]
        )
        return True
    
    def clear(self) -> int:
        """Clear all memories."""
        # Get all IDs
        results = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000
        )
        ids = [r.id for r in results[0]]
        
        if ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=ids
            )
        
        return len(ids)
    
    def count(self) -> int:
        """Count total memories."""
        return self.client.count(
            collection_name=self.collection_name
        ).count
