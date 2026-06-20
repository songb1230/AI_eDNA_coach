#!/bin/bash
# AI-GLCS Startup Script
# Usage: ./run.sh
# Requires: Python 3.9+ and Ollama running locally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"

echo "╔══════════════════════════════════════╗"
echo "║   AI-GLCS — Lab-Skill Coaching      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Ollama setup note
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "ℹ️  Optional: create $BACKEND_DIR/.env to customize Ollama:"
  echo "   OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
  echo "   OLLAMA_MODEL=$OLLAMA_MODEL"
  echo ""
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "⚠️  Ollama CLI was not found."
  echo "   Finish installing Ollama, then run: ollama pull $OLLAMA_MODEL"
  echo ""
else
  if ! curl -fs "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
    echo "⚠️  Ollama does not seem to be running at $OLLAMA_BASE_URL."
    echo "   Start Ollama, then run: ollama pull $OLLAMA_MODEL"
    echo ""
  fi
fi

# Install dependencies
echo "📦 Installing backend dependencies..."
cd "$BACKEND_DIR"
python3 -m pip install -r requirements.txt -q

echo ""
echo "🚀 Starting AI-GLCS backend on http://localhost:8000"
echo "🧠 Using Ollama model: $OLLAMA_MODEL at $OLLAMA_BASE_URL"
echo "🌐 Open frontend at: file://$FRONTEND_DIR/index.html"
echo "📖 API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."
echo ""

# Start FastAPI backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
