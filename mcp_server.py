"""
MCP Server for Qdrant Memory.
Provides vector-based memory storage as an MCP server with HTTP+SSE transport.
"""
import os
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from qdrant_memory import QdrantMemory
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import asyncio

# Initialize memory
print("Initializing Qdrant memory...")
memory = QdrantMemory()
print("Memory initialized")

# Create MCP server
app = Server("qdrant-memory")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="memory_add",
            description="Add a memory to the vector store",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "memory_type": {"type": "string", "description": "Type of memory (context, decision, pattern, etc.)", "default": "context"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization", "default": []},
                    "source_agent": {"type": "string", "description": "Source agent name", "default": "unknown"},
                    "source_file": {"type": "string", "description": "Source file if applicable", "default": None}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="memory_query",
            description="Query memories by semantic similarity",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "memory_type": {"type": "string", "description": "Filter by memory type", "default": None},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags", "default": []},
                    "limit": {"type": "integer", "description": "Max results", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="memory_get",
            description="Get a specific memory by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "Memory ID to retrieve"}
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="memory_delete",
            description="Delete a memory by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "Memory ID to delete"}
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="memory_count",
            description="Count total memories",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="memory_clear",
            description="Clear all memories",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "memory_add":
            result = memory.add(
                content=arguments["content"],
                memory_type=arguments.get("memory_type", "context"),
                tags=arguments.get("tags", []),
                source_agent=arguments.get("source_agent", "unknown"),
                source_file=arguments.get("source_file")
            )
            return [TextContent(type="text", text=json.dumps({"memory_id": result, "status": "added"}))]
        
        elif name == "memory_query":
            results = memory.query(
                query=arguments["query"],
                memory_type=arguments.get("memory_type"),
                tags=arguments.get("tags", []),
                limit=arguments.get("limit", 10)
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "memory_get":
            result = memory.get(arguments["memory_id"])
            return [TextContent(type="text", text=json.dumps(result, indent=2) if result else "{}")]
        
        elif name == "memory_delete":
            result = memory.delete(arguments["memory_id"])
            return [TextContent(type="text", text=json.dumps({"status": "deleted" if result else "not_found"}))]
        
        elif name == "memory_count":
            count = memory.count()
            return [TextContent(type="text", text=json.dumps({"count": count}))]
        
        elif name == "memory_clear":
            count = memory.clear()
            return [TextContent(type="text", text=json.dumps({"cleared": count}))]
        
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# Create SSE server transport
sse_transport = SseServerTransport("/messages/")


async def handle_sse(request):
    """Handle SSE connections."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, {"type": "message"}
    ) as streams:
        await app.run(
            streams[0], streams[1], app.create_initialization_options()
        )


async def handle_messages(request):
    """Handle messages from client."""
    return await sse_transport.handle_post_message(request.scope, request.receive)


# Create Starlette app with SSE routes
starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8081"))
    print(f"Starting MCP server on port {port}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)
