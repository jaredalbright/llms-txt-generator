# Backend Workflow — Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Frontend)                                │
└──────┬──────────────────────┬───────────────────────┬───────────────────┘
       │                      │                       │
  POST /api/generate     GET /stream/{id}       POST /api/validate
       │                      │                       │
       ▼                      ▼                       ▼
┌──────────────┐     ┌───────────────┐      ┌─────────────────┐
│ create_job() │     │ stream_job()  │      │   validate()    │
│ routers/     │     │ routers/      │      │ routers/        │
│ generate.py  │     │ generate.py   │      │ validate.py     │
│              │     │               │      │                 │
│ • UUID job   │     │ • SSE via     │      │ • Pure logic    │
│ • Queue()    │     │   asyncio     │      │ • No I/O        │
│ • fire task  │     │   Queue       │      │                 │
└──────┬───────┘     └───────────────┘      └────────┬────────┘
       │                  ▲  (consumes events)       │
       ▼                  │                          ▼
┌──────────────────────────────────────┐   ┌─────────────────────┐
│         run_pipeline()               │   │ validate_llms_txt() │
│         services/pipeline.py         │   │ services/           │
│                                      │   │ validator.py        │
│  Orchestrates Steps 1–4, pushes      │   │                     │
│  progress events onto the Queue      │   │ Checks:             │
│                                      │   │ • H1 exists         │
└──┬───────────────────────────────────┘   │ • Blockquote exists │
   │                                       │ • No H3+ headings   │
   │                                       │ • Valid link format  │
   ▼                                       └─────────────────────┘
```

## Step 1: Crawl — `services/crawler.py`

```
INPUT:  url: str  (e.g. "https://example.com")
        ──────────────────────────────────
        │                                │
        ▼                                ▼
   GET /sitemap.xml              Fallback: BFS link crawl
   (httpx, 10s timeout)         (httpx, 30s timeout)
   Parse XML <loc> tags          Parse <a href> tags
        │                                │
        └────────┬───────────────────────┘
                 ▼
        Dedupe, same-domain filter, cap at MAX_PAGES (50)

OUTPUT: list[str]  — discovered URLs
SSE:    {type: "progress", status: "crawling", pages_found: N}
I/O:    HTTP GET → target website (sitemap.xml + homepage)
```

## Step 2: Extract Metadata — `services/extractor.py`

```
INPUT:  list[str]  — URLs from Step 1
                 │
                 ▼  (sequential loop, one URL at a time)
        GET each URL (httpx, 15s timeout)
        Parse HTML with BeautifulSoup:
          • <title>         → title
          • <meta name="description"> → description
          • <meta property="og:description"> → fallback
          • <h1>            → h1

OUTPUT: list[PageMeta(url, title, description, h1)]
SSE:    {type: "progress", status: "processing", message: "Analyzing..."}
I/O:    HTTP GET → target website (each discovered page)
```

## Step 3: LLM Categorization — `services/llm/*.py` + `prompts/categorize.py`

```
INPUT:  site_url: str
        pages: list[PageMeta]
        client_info: str | None
                 │
        ┌────────┴────────┐
        ▼                 ▼
   MOCK_LLM=true     MOCK_LLM=false
   testing/           services/llm/
   mock_llm.py        factory.py → anthropic.py OR openai.py
   (fixture data)          │
                           ▼
                  ┌──────────────────────────┐
                  │ Anthropic or OpenAI API   │
                  │                          │
                  │ System: categorize.py     │
                  │   SYSTEM_PROMPT          │
                  │ User: build_user_prompt() │
                  │   "Analyze this website…" │
                  │   + page list             │
                  └──────────┬───────────────┘
                             ▼
                     Parse JSON response

OUTPUT: dict {
          site_name: str,
          summary: str,
          context: str | None,
          sections: [{name, pages: [{title, url, description}]}]
        }
I/O:    HTTP POST → Anthropic API or OpenAI API
```

## Step 4: Assemble Markdown — `services/generator.py`

```
INPUT:  structured_data: dict  (from Step 3)
                 │
                 ▼
        Build markdown string:
          # {site_name}
          > {summary}
          {context}
          ## {section.name}
          - [title](url): description
          ...

OUTPUT: str  — valid llms.txt markdown
I/O:    None (pure transformation)
```

## Step 5: Complete & Stream

```
INPUT:  markdown: str  (from Step 4)
                 │
                 ▼
        • job["status"] = "completed"
        • job["markdown"] = markdown
        • Queue.put({type: "complete", markdown: ...})
        • TODO: persist to Supabase

OUTPUT: SSE event → client receives final markdown
I/O:    In-memory dict update (Supabase stubbed)
```

---

## Reprompt Flow — `POST /api/reprompt`

```
INPUT:  {job_id, instruction, current_markdown}
                 │
        ┌────────┴────────┐
        ▼                 ▼
   MOCK_LLM=true     MOCK_LLM=false
   Append comment     llm.reprompt()
                       │
                       ▼
              prompts/reprompt.py
              → Anthropic/OpenAI API
              "Here's the current llms.txt,
               apply this instruction: ..."

OUTPUT: {markdown: str}  — modified markdown
I/O:    HTTP POST → LLM API
```

---

## File → Responsibility Map

| File | Role |
|------|------|
| `app/main.py` | FastAPI app init, CORS, request logging middleware |
| `app/config.py` | Pydantic `BaseSettings` — all env vars |
| `app/models.py` | Pydantic models: `GenerateRequest`, `PageMeta`, `ValidationIssue`, etc. |
| `app/routers/generate.py` | `/api/generate`, `/api/generate/{id}/stream`, `/api/reprompt` |
| `app/routers/validate.py` | `/api/validate` |
| `app/services/pipeline.py` | Orchestrator — calls Steps 1→4, manages Queue events |
| `app/services/crawler.py` | Step 1 — sitemap + BFS URL discovery |
| `app/services/extractor.py` | Step 2 — HTML metadata extraction |
| `app/services/llm/base.py` | Abstract `LLMProvider` (categorize + reprompt) |
| `app/services/llm/factory.py` | Returns Anthropic or OpenAI provider from config |
| `app/services/llm/anthropic.py` | Anthropic API calls |
| `app/services/llm/openai.py` | OpenAI API calls |
| `app/services/generator.py` | Step 4 — dict → markdown assembly |
| `app/services/validator.py` | Markdown spec compliance checker |
| `app/prompts/categorize.py` | System + user prompts for categorization |
| `app/prompts/reprompt.py` | System + user prompts for reprompting |
| `app/testing/mock_llm.py` | Fixture data (bypasses LLM when `MOCK_LLM=true`) |
| `app/db/client.py` | Supabase client stub (`NotImplementedError`) |
| `app/db/jobs.py` | Job persistence stubs (TODO) |

## All External I/O Summary

| Target | Protocol | Where | Purpose |
|--------|----------|-------|---------|
| Target website | HTTP GET | `crawler.py`, `extractor.py` | Sitemap, pages, metadata |
| Anthropic API | HTTP POST | `llm/anthropic.py` | Categorize pages, reprompt |
| OpenAI API | HTTP POST | `llm/openai.py` | Categorize pages, reprompt |
| Supabase | — | `db/client.py` | **Stubbed / not implemented** |
| Client browser | SSE | `routers/generate.py` | Stream progress + result |

## Configuration & Environment Variables

All via `app/config.py` → `BaseSettings` from `pydantic_settings`:

| Var | Default | Usage |
|-----|---------|-------|
| `LLM_PROVIDER` | `"anthropic"` | Selects Anthropic vs OpenAI |
| `ANTHROPIC_API_KEY` | `""` | Auth for Anthropic API |
| `OPENAI_API_KEY` | `""` | Auth for OpenAI API |
| `LLM_MODEL` | `"claude-sonnet-4-20250514"` | LLM model to use |
| `SUPABASE_URL`, `SUPABASE_KEY` | `""` | Database (not yet used) |
| `MAX_PAGES` | `50` | URL discovery cap |
| `CRAWL_TIMEOUT` | `30` | Seconds per page GET |
| `MOCK_LLM` | `True` | Skip real LLM, use fixtures |
| `FRONTEND_URL` | `"http://localhost:5173"` | CORS allowed origin |

## Error Handling

All errors in `run_pipeline()` are caught at the top level:

- Log stack trace
- Set job status to `"error"`
- Queue SSE event: `{type: "error", message: "Generation failed: {error}"}`
- Stream closes with error

Example failures:

- Network timeout during crawl/extract → logged warning, pages skipped
- LLM API error → caught, error queued to client
- Invalid JSON from LLM → `json.loads()` exception → caught at pipeline level
