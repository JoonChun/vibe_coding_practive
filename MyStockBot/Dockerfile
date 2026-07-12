# Build stage: Python 3.11 slim image as base
FROM python:3.11-slim

# Set timezone and install tzdata for APScheduler
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Seoul

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code (using .dockerignore to exclude unnecessary files)
COPY . .

# Expose port
EXPOSE 8000

# Start uvicorn with single worker (required for APScheduler and Phase 2 WebSocket)
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
