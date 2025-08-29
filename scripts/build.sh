#!/bin/bash

# Build script for Umbra Bot System
# Ensures proper build order: shared → services

set -e

echo "🔨 Building Umbra Bot System..."

# Build shared package first
echo "📦 Building shared package..."
cd shared
npm install
npm run build:clean
cd ..

echo "✅ Shared package built successfully"

# Build services in parallel
echo "🚀 Building services..."
(cd services/umbra && npm install) &
(cd services/finance && npm install) &
(cd services/concierge && npm install) &

wait

echo "✅ All dependencies installed"

# Note: Individual service builds will happen during Docker build or deployment
echo "🎉 Build preparation complete!"
echo ""
echo "🐳 To test Docker builds:"
echo "  docker build -f services/umbra/Dockerfile -t umbra ."
echo "  docker build -f services/finance/Dockerfile -t finance ."
echo "  docker build -f services/concierge/Dockerfile -t concierge ."
echo ""
echo "🚂 For Railway deployment, use the root railway.json configuration"
echo "🔍 To verify Railway configuration: ./scripts/verify-railway-config.sh"