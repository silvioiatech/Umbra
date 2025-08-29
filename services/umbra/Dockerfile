# Multi-stage build for TypeScript monorepo
FROM node:20-alpine AS base

# Set working directory
WORKDIR /app

# Copy package.json files for better Docker layer caching
COPY package*.json ./
COPY tsconfig.json ./
COPY shared/package*.json ./shared/
COPY services/umbra/package*.json ./services/umbra/

# Install all dependencies using workspace
RUN npm install --include=dev

# Copy shared source code first
COPY shared/ ./shared/

# Build shared package (force clean build) using node to run tsc
RUN cd shared && rm -f tsconfig.tsbuildinfo && node ../node_modules/typescript/lib/tsc.js --build

# Copy service source code
COPY services/umbra/src ./services/umbra/src
COPY services/umbra/tsconfig.json ./services/umbra/

# Build the service using node to run tsc
RUN cd services/umbra && node ../../node_modules/typescript/lib/tsc.js

# Production stage
FROM node:20-alpine AS production

WORKDIR /app

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Copy built application
COPY --from=base /app/services/umbra/dist ./dist
COPY --from=base /app/services/umbra/package*.json ./

# Copy built shared package as a dependency
COPY --from=base /app/shared/dist ./node_modules/@umbra/shared/dist
COPY --from=base /app/shared/package.json ./node_modules/@umbra/shared/

# Install only production dependencies
RUN npm ci --only=production --no-audit --no-fund && \
    npm cache clean --force

# Set proper ownership
RUN chown -R nodejs:nodejs /app
USER nodejs

# Environment variables
ENV NODE_ENV=production
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check using Node.js built-in net module
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('net').createConnection(8080, 'localhost').on('connect', () => process.exit(0)).on('error', () => process.exit(1))"

# Start the service
CMD ["npm", "start"]