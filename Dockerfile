FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./

# Install LanceDB native library for Linux ARM64
RUN npm install --omit=dev && \
    npm install @lancedb/vectordb-linux-arm64-musl

# Copy source
COPY index.js ./

# Create data directory
RUN mkdir -p /app/data

# Run in SSE mode
CMD ["node", "index.js"]
