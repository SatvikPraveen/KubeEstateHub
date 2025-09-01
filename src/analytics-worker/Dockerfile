# Location: `/src/analytics-worker/Dockerfile`

FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CELERY_BROKER_URL=redis://redis-service:6379/2 \
    CELERY_RESULT_BACKEND=redis://redis-service:6379/1

# Create non-root user
RUN groupadd -r analytics && useradd -r -g analytics -u 1001 analytics

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /tmp /var/cache /var/log /app/data && \
    chown -R analytics:analytics /app /tmp /var/cache /var/log

# Switch to non-root user
USER analytics

# Expose metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9090')" || exit 1

# Run the worker
CMD ["python", "worker.py"]