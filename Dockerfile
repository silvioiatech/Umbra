# Dockerfile for Umbra Bot - Phase 1
# Python-only implementation without Maven dependencies

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies required for psutil and future OCR (optional)
# Tesseract is commented out for Phase 1 but can be enabled for Phase 2+
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Optional: Uncomment for Phase 2+ OCR support
# RUN apt-get update && apt-get install -y \
#     tesseract-ocr \
#     tesseract-ocr-eng \
#     libtesseract-dev \
#     libgl1-mesa-glx \
#     libglib2.0-0 \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY umbra/ ./umbra/
COPY assessment_plan.py .

# Create non-root user for security
RUN groupadd -r umbra && useradd -r -g umbra umbra
RUN chown -R umbra:umbra /app
USER umbra

# Create data directories with appropriate permissions
RUN mkdir -p /app/data/finance /app/data/logs
VOLUME ["/app/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; from umbra.core.config import get_config; get_config(); print('OK')" || exit 1

# Expose port for future webhook mode (Phase 2+)
# EXPOSE 8080

# Default command - run the bot in polling mode
CMD ["python", "-m", "umbra.bot"]

# Alternative commands for different modes:
# CMD ["python", "-c", "from umbra import UmbraBot; import asyncio; bot = UmbraBot(); asyncio.run(bot.initialize() and bot.start_polling())"]

# Build instructions:
# docker build -t umbra-bot:phase1 .
# 
# Run instructions:
# docker run -e TELEGRAM_BOT_TOKEN=your_token \
#            -e ALLOWED_USER_IDS=123456789,987654321 \
#            -v $(pwd)/data:/app/data \
#            umbra-bot:phase1