"""
MCP Server for Qdrant Memory.
Provides vector-based memory storage as an MCP server.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from qdrant_memory import QdrantMemory
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import AnyUrl
import json

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


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
