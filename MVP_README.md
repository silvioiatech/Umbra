# UMBRA Telegram Bot MVP

A simple, production-ready Telegram bot demonstrating essential features including polling functionality, command handling, rate limiting, and comprehensive logging.

## Features

✅ **Polling Functionality** - Real-time message processing using Telegram's polling API  
✅ **Essential Commands** - `/start` and `/help` commands with proper handling  
✅ **Rate Limiting** - Built-in protection against spam (10 requests per minute per user)  
✅ **Comprehensive Logging** - Structured logging for monitoring and debugging  
✅ **User Authorization** - Optional access control via user ID allowlists  
✅ **Graceful Error Handling** - Robust error handling and recovery  

## Quick Start

### 1. Prerequisites

- Python 3.8+
- A Telegram bot token (get from [@BotFather](https://t.me/BotFather))

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/silvioiatech/UMBRA.git
cd UMBRA

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Set your bot token as an environment variable:

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
```

Optional - restrict access to specific users:

```bash
export ALLOWED_USER_IDS="123456789,987654321"  # comma-separated user IDs
```

To get your user ID, message [@userinfobot](https://t.me/userinfobot) on Telegram.

### 4. Run the Bot

```bash
python bot_mvp.py
```

You should see:

```
==================================================
🤖 UMBRA Telegram Bot MVP
==================================================
✅ Polling functionality
✅ /start and /help commands
✅ Rate limiting (10 req/min)
✅ Comprehensive logging
==================================================
2025-09-05 10:00:00 - bot_mvp - INFO - 🤖 UMBRA Bot MVP initialized
2025-09-05 10:00:00 - bot_mvp - INFO - 🚀 Starting UMBRA Bot MVP...
2025-09-05 10:00:00 - bot_mvp - INFO - ✅ Handlers registered
2025-09-05 10:00:00 - bot_mvp - INFO - ✅ UMBRA Bot MVP started successfully!
2025-09-05 10:00:00 - bot_mvp - INFO - 🔄 Polling for updates...
```

### 5. Test the Bot

1. Find your bot on Telegram (using the username you set with @BotFather)
2. Send `/start` to get a welcome message
3. Send `/help` to see available commands
4. Send any message to see the echo response

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with bot status and uptime |
| `/help` | Show help information and rate limit status |

## Architecture

### Core Components

- **UmbraBotMVP**: Main bot class handling all functionality
- **Rate Limiting**: Built-in protection using token bucket algorithm
- **Logging**: Structured logging with configurable levels
- **Authorization**: Optional user access control

### Rate Limiting

- **Limit**: 10 requests per minute per user
- **Algorithm**: Token bucket with sliding window
- **Behavior**: Graceful rejection with informative messages

### Logging

All interactions are logged including:
- User commands and messages
- Rate limit violations
- Authorization attempts
- Bot startup/shutdown events

### Error Handling

- Graceful handling of unauthorized users
- Rate limit exceeded notifications
- Comprehensive error logging
- Automatic recovery from transient failures

## Testing

Run the test suite to verify functionality:

```bash
# Run tests (bypasses config validation)
UMBRA_SKIP_VALIDATION=1 python test_mvp.py
```

Expected output:
```
🤖 UMBRA Bot MVP - Test Suite
========================================
🔍 Testing imports...
✅ Rate limiter imported successfully
✅ Logger imported successfully
✅ python-telegram-bot imported successfully

🔍 Testing rate limiter...
✅ Request 1 allowed, 2 remaining
✅ Request 2 allowed, 1 remaining
✅ Request 3 allowed, 0 remaining
✅ 4th request correctly denied (rate limited)

🔍 Testing logger...
✅ Logger test completed

🔍 Testing configuration...
✅ User ID parsing works: [123, 456, 789]

🔍 Testing MVP bot class...
✅ MVP bot class instantiated successfully
✅ Rate limiter configured: 10 requests per 60s
✅ User access configured: 2 allowed users
✅ User authorization working (allowed user)
✅ User authorization working (denied user)

========================================
📊 Test Results: 5/5 tests passed
🎉 All tests passed! MVP is ready to run.
```

## Configuration Options

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather | `1234567890:ABCD...` |
| `ALLOWED_USER_IDS` | No | Comma-separated user IDs | `123456789,987654321` |

### Default Behavior

- **No ALLOWED_USER_IDS**: Open access mode (all users allowed)
- **With ALLOWED_USER_IDS**: Restricted access (only listed users allowed)

## Production Deployment

### Environment Setup

```bash
# Production environment variables
export TELEGRAM_BOT_TOKEN="your_production_token"
export ALLOWED_USER_IDS="authorized_user_ids"

# Optional: Configure logging
export LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

### Process Management

Use a process manager like systemd, supervisor, or Docker for production deployment:

```bash
# Simple background process
nohup python bot_mvp.py > bot.log 2>&1 &

# Or use systemd, Docker, etc.
```

### Monitoring

The bot provides comprehensive logging for monitoring:

- All user interactions are logged with user IDs
- Rate limit violations are tracked
- Error conditions are logged with stack traces
- Bot uptime is tracked and displayed

## Security Features

1. **User Authorization**: Optional allowlist-based access control
2. **Rate Limiting**: Protection against spam and abuse
3. **Input Validation**: Safe handling of user input
4. **Logging**: Complete audit trail of all interactions

## Extending the MVP

The MVP is designed to be easily extensible:

1. **Add Commands**: Register new CommandHandler instances
2. **Add Features**: Extend the UmbraBotMVP class
3. **Custom Rate Limiting**: Modify rate limiter parameters
4. **Enhanced Logging**: Add custom log formatters

## Troubleshooting

### Common Issues

**Bot doesn't start:**
- Check that `TELEGRAM_BOT_TOKEN` is set correctly
- Verify the token is valid and the bot is not deleted

**Rate limiting too strict:**
- Modify `max_requests` and `window_seconds` in the RateLimiter initialization

**Users can't access:**
- Check `ALLOWED_USER_IDS` configuration
- Use open access mode by not setting `ALLOWED_USER_IDS`

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG python bot_mvp.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.