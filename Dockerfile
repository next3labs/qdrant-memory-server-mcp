FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source
COPY index.js ./

# Create data directory
RUN mkdir -p /app/data

# Run in SSE mode
CMD ["node", "index.js"]
