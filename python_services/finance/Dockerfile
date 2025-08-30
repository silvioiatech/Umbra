# Multi-stage build for Python Finance service
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies for OCR and image processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-por \
    libopencv-dev \
    python3-opencv \
    poppler-utils \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package first
COPY python_services/shared/ ./shared/

# Copy service files
COPY python_services/finance/ ./finance/

# Install shared package
RUN cd shared && pip install -e .

# Install service dependencies
RUN cd finance && pip install -e .

# Production stage
FROM python:3.11-slim AS production

# Create non-root user for security
RUN groupadd -g 1001 -r finance && \
    useradd -r -g finance -u 1001 finance

WORKDIR /app

# Install runtime dependencies for OCR and image processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-por \
    libopencv-dev \
    python3-opencv \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from base stage
COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/
COPY --from=base /app/ ./

# Create uploads directory for temporary files
RUN mkdir -p /tmp/uploads && chown finance:finance /tmp/uploads

# Set proper ownership
RUN chown -R finance:finance /app
USER finance

# Environment variables
ENV PYTHONPATH=/app
ENV PORT=8081

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Start the service
CMD ["python", "-m", "uvicorn", "finance.finance_service.main:app", "--host", "0.0.0.0", "--port", "8081"]