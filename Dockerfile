# Backend Dockerfile for School Ops
# Multi-stage build for optimized production image
# 
# Local workflow: uv sync → uv run uvicorn app.main:app
# This Dockerfile mirrors that workflow for consistency

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
# - gcc & libpq-dev: Required for psycopg2 compilation (if not using binary)
# - libffi-dev: Required for cryptography/bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into .venv
# --frozen: Use exact versions from uv.lock
# --no-install-project: Don't install the project itself yet
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application code
COPY . .

# Now install the project (if it's a package) - this ensures all deps are ready
RUN uv sync --frozen --no-dev

# Make venv world-accessible (fixes Railway/other PaaS permission issues)
RUN chmod -R a+rX /app/.venv && chmod -R a+x /app/.venv/bin

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
# - libpq5: PostgreSQL client library (runtime)
# - libffi8: FFI library (runtime for cryptography)
# - curl: For health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libffi8 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder (with fixed permissions)
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app /app

# Make everything world-readable (Railway runs as arbitrary user)
RUN chmod -R a+rX /app && chmod -R a+x /app/.venv/bin

# Environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Production defaults (can override via docker run -e or docker-compose)
ENV PORT=8000
ENV WORKERS=2

# Expose port (Railway will set PORT dynamically)
EXPOSE 8000

# Start uvicorn directly (matches local: uv run uvicorn app.main:app)
# Using shell form to expand $PORT at runtime
CMD /app/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}
