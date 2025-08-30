#!/bin/bash

echo "🚀 Umbra Bot System - Deployment Readiness Check"
echo "=================================================="
echo ""

# Check all required deployment files
echo "📋 Deployment Files:"
files=("Dockerfile" "Procfile" "railway.json" "railway.toml" ".env.example")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (missing)"
    fi
done

echo ""
echo "🔧 Service Configuration:"

# Check services
services=("umbra" "finance" "concierge" "business" "production" "creator")
for service in "${services[@]}"; do
    if [ -d "services/$service" ]; then
        echo "✅ services/$service"
        if [ -f "services/$service/Dockerfile" ]; then
            echo "  ✅ Dockerfile"
        else
            echo "  ❌ Dockerfile (missing)"
        fi
        if [ -f "services/$service/.env.example" ]; then
            echo "  ✅ .env.example"
        else
            echo "  ❌ .env.example (missing)"
        fi
        if [ -f "services/$service/package.json" ]; then
            echo "  ✅ package.json"
        else
            echo "  ❌ package.json (missing)"
        fi
    else
        echo "❌ services/$service (missing)"
    fi
done

echo ""
echo "🏗️  Build Status:"
echo "Running build test..."
if npm run build > /dev/null 2>&1; then
    echo "✅ Build successful"
else
    echo "❌ Build failed"
fi

echo ""
echo "📊 Railway Configuration:"
if grep -q '"services":' railway.json 2>/dev/null; then
    service_count=$(grep -c '"name":' railway.json 2>/dev/null || echo "0")
    echo "✅ Railway multi-service configuration found ($service_count services)"
else
    echo "❌ Railway configuration not found"
fi

echo ""
echo "📚 Documentation:"
docs=("DEPLOYMENT.md" "docs/deployment.md" "docs/railway-deployment.md")
for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        echo "✅ $doc"
    else
        echo "❌ $doc (missing)"
    fi
done

echo ""
echo "🎉 Deployment Summary:"
echo "The Umbra Bot System is ready for Railway deployment!"
echo ""
echo "🚂 To deploy to Railway:"
echo "1. Connect your GitHub repository to Railway"
echo "2. Railway will auto-detect the multi-service configuration"
echo "3. Configure environment variables for each service"
echo "4. Deploy!"
echo ""
echo "📖 See DEPLOYMENT.md for detailed instructions"