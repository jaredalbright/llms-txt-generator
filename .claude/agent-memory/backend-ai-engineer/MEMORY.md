# Backend Engineer Memory

## Environment
- Python 3.14.2 (use `python3`, NOT `python`)
- **venv**: `backend/.venv/` — activate with `source backend/.venv/bin/activate`
- Run server: `cd backend && uvicorn app.main:app --reload` (port 8000)
- Run tests: `cd backend && python3 -m pytest tests/`
- Install deps: `pip install -e ".[dev]"` (from `backend/`)
- Config: pydantic-settings reads `backend/.env` (see `.env.example`)

## Project Structure
- Backend root: `backend/`
- FastAPI app entry: `app/main.py` with `app` instance
- Config via pydantic-settings: `app/config.py` (reads `.env`)
- Routes: `app/routers/generate.py` (POST /api/generate, GET /api/generate/{id}/stream, POST /api/reprompt), `app/routers/validate.py` (POST /api/validate)
- Models/schemas: `app/models/base.py`, `app/models/generation.py`
- Services: `app/services/` — generator, html, http, progress, url_utils, validator
- Pipeline: `app/services/pipeline/` — dag.py, node.py, nodes.py
- LLM providers: `app/services/llm/` with abstract base, anthropic, openai, factory pattern
- Prompts: `app/prompts/` — categorize.py, summarize.py
- DB layer: `app/db/` — client.py, memory.py (in-memory store), repository.py, generation_store.py (Supabase stubbed)
- Testing: `app/testing/mock_llm.py`, `backend/tests/`

## Key Patterns
- In-memory job store — will migrate to Supabase
- SSE streaming via sse-starlette + asyncio.Queue per job
- LLM provider abstraction: base.py ABC → anthropic.py/openai.py, selected via factory.py
- Pipeline: crawl → extract metadata → LLM categorize → assemble markdown
- Prompts stored in `app/prompts/` as module-level constants + builder functions
- MOCK_LLM=true env var skips real LLM calls (uses mock_llm.py)

## API Routes
- `GET /health` — health check
- `POST /api/generate` — start generation job, returns job_id
- `GET /api/generate/{job_id}/stream` — SSE stream for job progress
- `POST /api/reprompt` — modify existing markdown via LLM
- `POST /api/validate` — validate llms.txt markdown against spec

## Environment Variables
- `LLM_PROVIDER` (anthropic/openai), `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LLM_MODEL`
- `MOCK_LLM` (true/false), `MAX_PAGES` (default 50), `CRAWL_TIMEOUT` (default 30)
- `FRONTEND_URL` (default http://localhost:5173)
- `SUPABASE_URL`, `SUPABASE_KEY` (not yet configured)

## Dependencies (pyproject.toml)
fastapi, uvicorn[standard], httpx, beautifulsoup4, lxml, anthropic, openai, sse-starlette, pydantic-settings, supabase, markdownify, python-dotenv
Dev: pytest, pytest-asyncio
