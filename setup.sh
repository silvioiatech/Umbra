#!/bin/bash

# UMBRA Setup Script
# ==================
# This script helps set up the UMBRA bot for development and testing

echo "🚀 UMBRA Setup Script"
echo "===================="

# Check Python version
echo "🐍 Checking Python version..."
python3 --version

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Create data directory
echo "📁 Creating data directory..."
mkdir -p data

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env file not found - using .env.example"
    cp .env.example .env
    echo "📝 Please edit .env file with your configuration"
else
    echo "✅ .env file exists"
fi

# Run system test
echo "🧪 Running system test..."
python3 system_test.py

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo "1. Edit .env file with your real credentials:"
echo "   - TELEGRAM_BOT_TOKEN (from @BotFather)"
echo "   - ALLOWED_USER_IDS (from @userinfobot)"
echo "   - ALLOWED_ADMIN_IDS"
echo ""
echo "2. Optional - Add API keys for enhanced features:"
echo "   - OPENROUTER_API_KEY (for AI features)"
echo "   - R2_* variables (for cloud storage)"
echo ""
echo "3. Start the bot:"
echo "   python3 main.py"
echo ""
echo "4. Test in Telegram:"
echo "   /start"
echo "   /status"
echo "   /help"
echo ""
echo "📋 Current Status:"
python3 -c "
import os
print(f'Bot Token: {\"✅ Set\" if os.getenv(\"TELEGRAM_BOT_TOKEN\") and os.getenv(\"TELEGRAM_BOT_TOKEN\") != \"your_bot_token_here\" else \"❌ Not set\"}')
print(f'User IDs: {\"✅ Set\" if os.getenv(\"ALLOWED_USER_IDS\") and os.getenv(\"ALLOWED_USER_IDS\") != \"123456789\" else \"❌ Default values\"}')
print(f'OpenRouter: {\"✅ Set\" if os.getenv(\"OPENROUTER_API_KEY\") else \"⚠️ Optional\"}')
print(f'R2 Storage: {\"✅ Set\" if os.getenv(\"R2_ACCOUNT_ID\") else \"⚠️ Optional\"}')
"
