#!/bin/bash
set -e

# =============================================================================
# Entrypoint script for School Ops Backend
# =============================================================================
# This script handles:
# 1. Running database migrations (optional, controlled by RUN_MIGRATIONS env)
# 2. Starting the application server (gunicorn + uvicorn workers)
# =============================================================================

echo "=========================================="
echo "School Ops Backend - Starting Up"
echo "=========================================="

# Default values
PORT=${PORT:-8000}
WORKERS=${WORKERS:-4}
RUN_MIGRATIONS=${RUN_MIGRATIONS:-true}

# Wait for database to be ready (simple retry loop)
wait_for_db() {
    echo "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if python -c "
from app.core.config import settings
from sqlalchemy import create_engine, text
try:
    engine = create_engine(str(settings.DATABASE_URL))
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    exit(0)
except Exception as e:
    print(f'Attempt $attempt: Database not ready - {e}')
    exit(1)
" 2>/dev/null; then
            echo "Database is ready!"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: Database not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "ERROR: Database connection failed after $max_attempts attempts"
    exit 1
}

# Run database migrations
run_migrations() {
    if [ "$RUN_MIGRATIONS" = "true" ]; then
        echo "Running database migrations..."
        alembic upgrade head
        echo "Migrations completed successfully!"
    else
        echo "Skipping migrations (RUN_MIGRATIONS=$RUN_MIGRATIONS)"
    fi
}

# Start the application server
start_server() {
    echo "Starting server on port $PORT with $WORKERS workers..."
    echo "=========================================="
    
    # Use exec to replace the shell process with gunicorn
    # This ensures proper signal handling (SIGTERM, SIGINT)
    exec gunicorn app.main:app \
        --workers "$WORKERS" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "0.0.0.0:$PORT" \
        --access-logfile - \
        --error-logfile - \
        --capture-output \
        --enable-stdio-inheritance \
        --timeout 120 \
        --keep-alive 5 \
        --graceful-timeout 30
}

# Main execution
main() {
    wait_for_db
    run_migrations
    start_server
}

# Handle if custom command is passed (e.g., docker run ... bash)
if [ "$#" -gt 0 ]; then
    exec "$@"
else
    main
fi
