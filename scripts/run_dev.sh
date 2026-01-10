#!/bin/bash
# Script to run development server

# Set working directory
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying from env.example..."
    cp env.example .env
    echo "Please edit .env and add your OPENAI_API_KEY"
fi

# Initialize database tables
echo "Initializing database..."
python scripts/init_db.py

# Run development server
echo "Starting development server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

