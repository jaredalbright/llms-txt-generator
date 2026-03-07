# llms.txt Generator

A web application that takes a URL as input, crawls the target website, extracts metadata, uses an LLM to categorize and summarize the pages, and produces a spec-compliant [llms.txt](https://llmstxt.org/) file the user can edit, reprompt, and download.

## Architecture

- **Frontend**: React + Vite + Tailwind CSS (TypeScript)
- **Backend**: FastAPI + Python
- **LLM Providers**: Anthropic Claude / OpenAI GPT (swappable)
- **Database**: Supabase (PostgreSQL) — stubbed, using in-memory storage for now

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Fill in your API keys in .env
uvicorn app.main:app --reload
```

The API server runs at `http://localhost:8000`. Check health at `/health`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies `/api` requests to the backend.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start a new generation job |
| `GET` | `/api/generate/{job_id}/stream` | SSE stream for job progress |
| `POST` | `/api/reprompt` | Modify existing markdown via LLM |
| `POST` | `/api/validate` | Validate llms.txt against spec |
| `GET` | `/health` | Health check |

## Deployment

- **Frontend** → Vercel (root directory: `frontend`, framework: Vite)
- **Backend** → Railway (root directory: `backend`, start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
- **Database** → Supabase

Set `VITE_API_URL` on Vercel to your Railway backend URL. Set `FRONTEND_URL` on Railway to your Vercel domain.

## Running Tests

```bash
cd backend
pip install -e ".[dev]"
pytest tests/
```
