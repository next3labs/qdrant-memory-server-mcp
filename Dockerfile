FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install --omit=dev

# Copy source
COPY index.js ./

# Create data directory
RUN mkdir -p /app/data

# Run in SSE mode
CMD ["node", "index.js"]
