# AI-GLCS

AI-Guided Lab-Skill Coaching System: a FastAPI backend with a static React frontend for guided lab procedure coaching, assessment, and progress tracking. The backend uses local Ollama models by default.

## Prerequisites

- Python 3.9+
- Ollama running locally
- An Ollama model such as `llama3.2`

## Run Locally

```bash
./run.sh
```

The script installs backend dependencies, starts the FastAPI server at `http://localhost:8000`, and prints the local frontend file URL.

Optional backend settings can be placed in `backend/.env`:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Project Structure

```text
backend/    FastAPI API, SQLite persistence, Ollama integration
frontend/   Static React app
run.sh      Local startup script
```

