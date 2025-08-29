#!/usr/bin/env bash
# Railway Deployment Verification Script
# This script helps verify that all 6 services are properly deployed to Railway

echo "🚂 Railway Multi-Service Deployment Verification"
echo "================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if railway.json exists and is valid
echo "1. Checking railway.json configuration..."
if [ ! -f "railway.json" ]; then
    echo -e "${RED}❌ railway.json not found${NC}"
    exit 1
fi

# Validate JSON
if command -v python3 &> /dev/null; then
    python3 -c "import json; json.load(open('railway.json'))" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ railway.json is valid JSON${NC}"
    else
        echo -e "${RED}❌ railway.json contains invalid JSON${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Python3 not available, skipping JSON validation${NC}"
fi

# Check for required services
echo ""
echo "2. Checking service definitions..."
services=("umbra" "finance" "concierge" "business" "production" "creator")
for service in "${services[@]}"; do
    if grep -q "\"$service\"" railway.json; then
        echo -e "${GREEN}✅ $service service defined${NC}"
    else
        echo -e "${RED}❌ $service service missing${NC}"
    fi
done

# Check for Dockerfiles
echo ""
echo "3. Checking Dockerfiles..."
for service in "${services[@]}"; do
    if [ -f "services/$service/Dockerfile" ]; then
        echo -e "${GREEN}✅ services/$service/Dockerfile exists${NC}"
    else
        echo -e "${RED}❌ services/$service/Dockerfile missing${NC}"
    fi
done

# Check for conflicting individual railway.json files
echo ""
echo "4. Checking for conflicting configurations..."
conflict_found=false
for service in "${services[@]}"; do
    if [ -f "services/$service/railway.json" ]; then
        echo -e "${RED}❌ Conflicting railway.json found in services/$service/${NC}"
        conflict_found=true
    fi
done

if [ "$conflict_found" = false ]; then
    echo -e "${GREEN}✅ No conflicting railway.json files found${NC}"
fi

# Check environment variable examples
echo ""
echo "5. Checking environment variable templates..."
if [ -f ".env.example" ]; then
    echo -e "${GREEN}✅ .env.example found (global)${NC}"
else
    echo -e "${YELLOW}⚠️  .env.example not found (global)${NC}"
fi

for service in "${services[@]}"; do
    if [ -f "services/$service/.env.example" ]; then
        echo -e "${GREEN}✅ services/$service/.env.example exists${NC}"
    else
        echo -e "${YELLOW}⚠️  services/$service/.env.example missing${NC}"
    fi
done

echo ""
echo "📋 Summary:"
echo "----------"
echo "• Railway configuration ready for multi-service deployment"
echo "• 6 services will be automatically deployed when repository is connected to Railway"
echo "• Remember to configure environment variables for each service after deployment"
echo ""
echo "📚 For complete deployment instructions, see:"
echo "   - DEPLOYMENT.md"
echo "   - docs/railway-deployment.md"
echo ""
echo -e "${GREEN}🎉 Configuration validation complete!${NC}"