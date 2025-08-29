# Test Dockerfile
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
COPY shared/package*.json ./shared/
COPY services/umbra/package*.json ./services/umbra/
RUN npm install --include=dev
RUN find . -name "tsc*" -type f || echo "No tsc found"
RUN ls -la node_modules/typescript/bin/ || echo "No typescript bin dir"
RUN ls -la node_modules/typescript/lib/ || echo "No typescript lib dir"
