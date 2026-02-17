# Backend Dockerfile for School Ops
# Single-stage build for reliability
# 
# Local workflow: uv sync → uv run uvicorn app.main:app

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# - gcc & libpq-dev: Required for psycopg2 compilation
# - libffi-dev: Required for cryptography/bcrypt  
# - curl: For health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies using UV into system Python (no venv)
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code
COPY . .

# Make everything world-readable (Railway runs as arbitrary user)
RUN chmod -R a+rX /app

# Environment variables
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Production defaults (can override via docker run -e or docker-compose)
ENV PORT=8000
ENV WORKERS=2

# Expose port
EXPOSE 8000

# Start uvicorn with shell for variable expansion
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}"]
