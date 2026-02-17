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

# Copy UV for running commands (matches local workflow: uv run ...)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy virtual environment from builder (with fixed permissions)
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app /app

# Copy entrypoint script and make executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

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
ENV RUN_MIGRATIONS=false

# Expose port
EXPOSE 8000

# Health check using curl (simpler and more reliable)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/api/v1/health || exit 1

# Use entrypoint script for proper signal handling
ENTRYPOINT ["/app/entrypoint.sh"]
