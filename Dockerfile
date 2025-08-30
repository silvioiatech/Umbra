# Dockerfile for Umbra Complete - Python FastAPI Application
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OCR and image processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy the application files
COPY umbra_complete.py /app/umbra_complete.py
COPY test_umbra.py /app/test_umbra.py
COPY .env.example /app/.env.example

# Create directories for uploads and storage
RUN mkdir -p /app/uploads /app/storage /app/media

# Expose the port the app runs on
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Command to run the application
CMD ["python", "umbra_complete.py"]