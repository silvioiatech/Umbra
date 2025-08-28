#!/bin/bash

# Umbra Bot System Deployment Script
# This script sets up the complete Umbra Bot system

set -e

echo "🚀 Starting Umbra Bot System Deployment"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18+ is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Install dependencies
echo "📦 Installing dependencies..."
npm install
cd shared && npm install && npm run build && cd ..
echo "✅ Dependencies installed"

# Check environment variables
echo "🔧 Checking environment configuration..."

ENV_FILES=(
    "services/umbra/.env"
    "services/finance/.env" 
    "services/concierge/.env"
)

MISSING_ENV=false

for env_file in "${ENV_FILES[@]}"; do
    if [ ! -f "$env_file" ]; then
        echo "⚠️  Missing environment file: $env_file"
        echo "   Please copy from ${env_file}.example and configure"
        MISSING_ENV=true
    fi
done

if [ "$MISSING_ENV" = true ]; then
    echo ""
    echo "🔧 To create environment files:"
    echo "   cp services/umbra/.env.example services/umbra/.env"
    echo "   cp services/finance/.env.example services/finance/.env"
    echo "   cp services/concierge/.env.example services/concierge/.env"
    echo ""
    echo "Then edit each .env file with your configuration."
    exit 1
fi

echo "✅ Environment configuration found"

# Build Docker images
echo "🐳 Building Docker images..."
docker-compose build

echo "✅ Docker images built successfully"

# Start services
echo "🚀 Starting Umbra Bot System..."
docker-compose up -d

echo ""
echo "🎉 Umbra Bot System deployment completed!"
echo ""
echo "📊 Service Status:"
echo "   Umbra Main Agent: http://localhost:8080"
echo "   Finance Module:   http://localhost:8081"
echo "   Business Module:  http://localhost:8082"
echo "   Production Module: http://localhost:8083"
echo "   Creator Module:   http://localhost:8084"
echo "   MCP Service:      http://localhost:8085"
echo "   VPS Concierge:    http://localhost:9090"
echo ""
echo "🔍 Health Checks:"
echo "   curl http://localhost:8080/health"
echo "   curl http://localhost:8081/health"
echo ""
echo "📋 Next Steps:"
echo "   1. Configure your Telegram bot webhook"
echo "   2. Test document upload to Finance module"
echo "   3. Set up VPS access for Concierge"
echo "   4. Monitor logs: docker-compose logs -f"
echo ""
echo "🛠️  For development:"
echo "   docker-compose logs -f umbra"
echo "   docker-compose restart finance"
echo ""
echo "📚 Documentation: ./docs/"
echo "🆘 Support: Create an issue on GitHub"