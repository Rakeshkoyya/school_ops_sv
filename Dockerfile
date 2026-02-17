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
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 appuser

# Copy UV for running commands (matches local workflow: uv run ...)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app /app

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Change ownership to appuser
RUN chown -R appuser:appuser /app

# Environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Production defaults (can override via docker run -e or docker-compose)
ENV PORT=8000
ENV WORKERS=4
ENV RUN_MIGRATIONS=true

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check using curl (simpler and more reliable)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/api/v1/health || exit 1

# Use entrypoint script for proper signal handling
ENTRYPOINT ["/app/entrypoint.sh"]
