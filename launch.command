#!/bin/bash
# AI-GLCS — Single-click launcher
# Double-click this file to start the app.

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║   AI-GLCS — Launching...            ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Kill any previous backend on port 8000
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "⚠️  Stopping previous backend on port 8000..."
  lsof -ti:8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# Start backend in background, log to file
LOG="$DIR/backend.log"
echo "📦 Starting backend (log → backend.log)..."
cd "$DIR"
bash run.sh > "$LOG" 2>&1 &
BACKEND_PID=$!

# Wait up to 60 seconds for the server to respond
echo "⏳ Waiting for server on http://localhost:8000 ..."
for i in $(seq 1 60); do
  if curl -fs http://localhost:8000/docs >/dev/null 2>&1; then
    echo "✅ Server is up!"
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo ""
    echo "❌ Backend crashed. Check backend.log for details:"
    tail -20 "$LOG"
    echo ""
    echo "Press Enter to close."
    read
    exit 1
  fi
  printf "."
  sleep 1
done
echo ""

# Open the frontend
echo "🌐 Opening frontend..."
open "$DIR/frontend/index.html"

echo ""
echo "✅ AI-GLCS is running."
echo "   Frontend: file://$DIR/frontend/index.html"
echo "   Backend:  http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo "   Log file: $DIR/backend.log"
echo ""
echo "Close this window (or press Ctrl+C) to STOP the server."
echo ""

# Keep terminal open and wait for backend
wait $BACKEND_PID
echo ""
echo "Backend stopped. You can close this window."
