FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY qdrant_memory.py .
COPY mcp_server.py .

# Run MCP server
CMD ["python", "mcp_server.py"]
