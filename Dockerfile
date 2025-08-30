# Root Dockerfile for Railway deployment
# This serves as a fallback when Railway doesn't properly detect the multi-service configuration
# This builds the main umbra service (port 8080) as the primary application

FROM node:20-alpine

# Disable strict SSL checking for npm (workaround for cert issues)
RUN npm config set strict-ssl false

# Set working directory
WORKDIR /app

# Copy entire project for workspace setup
COPY package*.json ./
COPY tsconfig.json ./
COPY shared/ ./shared/
COPY services/umbra/ ./services/umbra/

# Install dependencies
RUN npm install --include=dev

# Build shared package first
RUN cd shared && npm run build

# Build the umbra service
RUN cd services/umbra && npm run build

# Environment variables
ENV NODE_ENV=production
ENV PORT=8080

# Expose port
EXPOSE 8080

# Change to service directory and start
WORKDIR /app/services/umbra
CMD ["npm", "start"]