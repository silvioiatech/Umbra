# Multi-stage build to handle shared package dependency
FROM node:20-alpine AS shared-builder

WORKDIR /app/shared
COPY shared/package*.json ./
RUN npm install

COPY shared/ ./
RUN npm run build

# Main service build
FROM node:20-alpine AS service-builder

WORKDIR /app

# Copy shared package from previous stage
COPY --from=shared-builder /app/shared /app/shared

# Copy service package files and install dependencies
COPY services/business/package*.json ./
RUN npm install

# Copy service source and build configuration
COPY services/business/src ./src
COPY services/business/tsconfig.json ./

# Build the application
RUN npm run build

# Production stage
FROM node:20-alpine

# Install curl for health checks
RUN apk add --no-cache curl

WORKDIR /app

# Copy only production dependencies and built code
COPY --from=service-builder /app/dist ./dist
COPY --from=service-builder /app/package*.json ./

# Install only production dependencies
RUN npm install --only=production && npm cache clean --force

# Expose port
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1

# Start the service
CMD ["npm", "start"]