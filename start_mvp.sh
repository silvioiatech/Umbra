#!/bin/bash
# UMBRA Bot MVP - Quick Start Script

echo "🤖 UMBRA Telegram Bot MVP - Quick Start"
echo "======================================"

# Check if bot token is provided
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN environment variable is required"
    echo ""
    echo "📝 Steps to get started:"
    echo "1. Go to https://t.me/BotFather on Telegram"
    echo "2. Send /newbot and follow instructions"
    echo "3. Copy the bot token provided"
    echo "4. Run: export TELEGRAM_BOT_TOKEN='your_token_here'"
    echo "5. Run this script again"
    echo ""
    echo "🔧 Optional: Restrict access to specific users"
    echo "   Get your user ID from @userinfobot"
    echo "   export ALLOWED_USER_IDS='123456789,987654321'"
    echo ""
    exit 1
fi

echo "✅ Bot token configured"

# Check if user restrictions are set
if [ -n "$ALLOWED_USER_IDS" ]; then
    echo "✅ User access restrictions: $ALLOWED_USER_IDS"
else
    echo "⚠️ Open access mode (no user restrictions)"
fi

echo ""
echo "🚀 Starting UMBRA Bot MVP..."
echo "📱 Your bot will be available on Telegram"
echo "💬 Available commands: /start, /help"
echo "⏱️ Rate limit: 10 requests per minute per user"
echo ""
echo "Press Ctrl+C to stop the bot"
echo ""

# Start the bot
python bot_mvp.py