# Backend Engineer Memory

## Project Structure
- Backend root: `/Users/jaredalbright/Projects/llms-txt-generator/backend/`
- FastAPI app entry: `app/main.py` with `app` instance
- Config via pydantic-settings: `app/config.py` (reads `.env`)
- Routes: `app/routers/generate.py` (POST /api/generate, GET /api/generate/{id}/stream, POST /api/reprompt), `app/routers/validate.py` (POST /api/validate)
- Models/schemas: `app/models.py`
- Services: `app/services/` — crawler, extractor, generator, validator, pipeline
- LLM providers: `app/services/llm/` with abstract base, anthropic, openai, factory pattern
- Prompts: `app/prompts/` — categorize, reprompt, summarize (TODO)
- DB layer: `app/db/` — client.py, jobs.py (both stubbed, awaiting Supabase setup)
- Tests: `backend/tests/`

## Key Patterns
- In-memory job store (dict in generate.py) — will migrate to Supabase
- SSE streaming via sse-starlette for job progress
- LLM provider abstraction: base.py ABC -> anthropic.py/openai.py, selected via factory.py
- Pipeline: crawl -> extract metadata -> LLM categorize -> assemble markdown
- Prompts stored in `app/prompts/` as module-level constants + builder functions

## API Routes
- `GET /health` — health check
- `POST /api/generate` — start generation job, returns job_id
- `GET /api/generate/{job_id}/stream` — SSE stream for job progress
- `POST /api/reprompt` — modify existing markdown via LLM
- `POST /api/validate` — validate llms.txt markdown against spec
