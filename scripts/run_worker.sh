#!/bin/bash
# Script to run Celery worker

# Set working directory
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run Celery worker
echo "Starting Celery worker..."
celery -A app.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --queues=celery \
    -E

