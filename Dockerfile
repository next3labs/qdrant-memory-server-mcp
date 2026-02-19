FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn pydantic qdrant-client sentence-transformers numpy

COPY server.py qdrant_memory.py ./

EXPOSE 8001

CMD ["python", "server.py"]
