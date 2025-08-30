# Multi-stage build for Python Umbra service
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package first
COPY python_services/shared/ ./shared/

# Copy service files
COPY python_services/umbra/ ./umbra/

# Install shared package
RUN cd shared && pip install -e .

# Install service dependencies
RUN cd umbra && pip install -e .

# Production stage
FROM python:3.11-slim AS production

# Create non-root user for security
RUN groupadd -g 1001 -r umbra && \
    useradd -r -g umbra -u 1001 umbra

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from base stage
COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/
COPY --from=base /app/ ./

# Set proper ownership
RUN chown -R umbra:umbra /app
USER umbra

# Environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the service
CMD ["python", "-m", "uvicorn", "umbra.umbra_service.main:app", "--host", "0.0.0.0", "--port", "8080"]