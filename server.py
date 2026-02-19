"""
Memory MCP server for OpenCode Forge.
Provides vector-based memory storage using Qdrant (local or cloud).
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


# Always use Qdrant - fail if not configured
from qdrant_memory import QdrantMemory
print("Initializing Qdrant memory...")
memory = QdrantMemory()
print("Qdrant memory initialized")


# Request/Response models
class AddMemoryRequest(BaseModel):
    content: str
    type: str = "context"
    tags: List[str] = []
    source_agent: str = "unknown"
    source_file: Optional[str] = None


class QueryMemoryRequest(BaseModel):
    query: str
    type: Optional[str] = None
    tags: List[str] = []
    limit: int = 10


app = FastAPI(
    title="OpenCode Forge Memory Server",
    description="Vector-based memory for OpenCode Forge agents",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "storage": "qdrant",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/stats")
async def get_stats():
    """Get memory statistics."""
    try:
        count = memory.count()
        return {
            "status": "success",
            "total_memories": count,
            "storage": "qdrant"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory")
async def add_memory(request: AddMemoryRequest):
    """Add a new memory to the vector store."""
    try:
        memory_id = memory.add(
            content=request.content,
            memory_type=request.type,
            tags=request.tags,
            source_agent=request.source_agent,
            source_file=request.source_file
        )
        
        return {
            "status": "success",
            "id": memory_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/query")
async def query_memory(request: QueryMemoryRequest):
    """Search memories by semantic similarity."""
    try:
        results = memory.query(
            query=request.query,
            memory_type=request.type,
            tags=request.tags,
            limit=request.limit
        )
        
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/{memory_id}")
async def get_memory(memory_id: str):
    """Get a specific memory by ID."""
    try:
        result = memory.get(memory_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {
            "status": "success",
            "memory": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory by ID."""
    try:
        memory.delete(memory_id)
        return {
            "status": "success",
            "id": memory_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/clear")
async def clear_memory():
    """Clear all memories."""
    try:
        count = memory.clear()
        return {
            "status": "success",
            "deleted_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the memory server."""
    port = int(os.environ.get("MEMORY_SERVER_PORT", "8001"))
    host = os.environ.get("MEMORY_SERVER_HOST", "0.0.0.0")
    
    storage_type = "Qdrant Cloud" if USE_QDRANT else "local"
    print(f"Starting OpenCode Forge Memory Server on {host}:{port}")
    print(f"Storage: {storage_type}")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
