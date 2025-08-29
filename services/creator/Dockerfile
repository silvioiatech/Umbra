# Multi-stage build for TypeScript monorepo with certificate workaround
FROM node:20-alpine AS base

# Disable strict SSL checking for npm (workaround for cert issues)
RUN npm config set strict-ssl false

# Set working directory
WORKDIR /app

# Copy root package.json for workspace configuration
COPY package*.json ./
COPY tsconfig.json ./

# Copy shared package configuration first for better caching
COPY shared/package*.json ./shared/
COPY services/creator/package*.json ./services/creator/

# Install all dependencies using workspace
RUN npm install --include=dev

# Copy shared source code first
COPY shared/ ./shared/

# Build shared package using npm script (avoids direct tsc issues)
RUN cd shared && npm run build

# Copy service source code
COPY services/creator/src ./services/creator/src
COPY services/creator/tsconfig.json ./services/creator/

# Build the service using npm script
RUN cd services/creator && npm run build

# Production stage
FROM node:20-alpine AS production

WORKDIR /app

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Copy built application
COPY --from=base /app/services/creator/dist ./dist
COPY --from=base /app/services/creator/package*.json ./

# Copy built shared package as a dependency
COPY --from=base /app/shared/dist ./node_modules/@umbra/shared/dist
COPY --from=base /app/shared/package.json ./node_modules/@umbra/shared/

# Install only production dependencies
RUN npm ci --only=production --no-audit --no-fund && \
    npm cache clean --force

# Create uploads directory for media generation
RUN mkdir -p /tmp/uploads && chown nodejs:nodejs /tmp/uploads

# Set proper ownership
RUN chown -R nodejs:nodejs /app
USER nodejs

# Environment variables
ENV NODE_ENV=production
ENV PORT=8084

# Expose port
EXPOSE 8084

# Health check using Node.js built-in net module
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('net').createConnection(8084, 'localhost').on('connect', () => process.exit(0)).on('error', () => process.exit(1))"

# Start the service
CMD ["npm", "start"]