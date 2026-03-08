# Backend Workflow — Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Frontend)                                    │
└──────┬──────────────────────┬───────────────────────┬──────────────┬────────┘
       │                      │                       │              │
  POST /api/generate     GET /stream/{id}       POST /api/validate   │
  {url, mode,            (SSE)                  {markdown}      GET /child-pages.zip
   client_info?}              │                       │              │
       │                      │                       │              │
       ▼                      ▼                       ▼              ▼
┌──────────────┐     ┌───────────────┐      ┌──────────────┐  ┌────────────────┐
│ create_job() │     │ stream_job()  │      │  validate()  │  │ download_      │
│ routers/     │     │ routers/      │      │ routers/     │  │ child_pages_   │
│ generate.py  │     │ generate.py   │      │ validate.py  │  │ zip()          │
│              │     │               │      │              │  │ routers/       │
│ • UUID job   │     │ • SSE via     │      │ • Pure logic │  │ generate.py    │
│ • Queue()    │     │   asyncio     │      │ • No I/O     │  │                │
│ • store mode │     │   Queue       │      │              │  │ • Builds zip   │
│ • fire task  │     │ • yields:     │      │              │  │   from stored  │
│              │     │   progress,   │      │              │  │   child_pages  │
│              │     │   complete,   │      │              │  │ • slugify()    │
│              │     │   error       │      │              │  │   for filenames│
└──────┬───────┘     └───────────────┘      └────────┬─────┘  └────────────────┘
       │                  ▲  (consumes events)       │
       ▼                  │                          ▼
┌──────────────────────────────────────┐   ┌─────────────────────┐
│         run_pipeline()               │   │ validate_llms_txt() │
│         services/pipeline.py         │   │ services/           │
│                                      │   │ validator.py        │
│  Orchestrates Steps 1–6, pushes      │   │                     │
│  progress events onto the Queue      │   │ Checks:             │
│                                      │   │ • H1 exists         │
│  Accepts mode: "parent_only"|"full"  │   │ • Blockquote exists │
│  Mode controls whether child pages   │   │ • No H3+ headings   │
│  are fetched and links rewritten     │   │ • Valid link format  │
│  to .md URLs                         │   │   (https:// required)│
└──┬───────────────────────────────────┘   └─────────────────────┘
   │
   ▼
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

## Step 4: Fetch Child Pages (full mode only) — `services/content_fetcher.py`

```
CONDITION: mode == "full"  (skipped entirely in "parent_only" mode)

INPUT:  child_urls: list[str]  — all page URLs from structured_data sections
                 │
                 ▼
        Concurrent fetch with asyncio.Semaphore(CONTENT_FETCH_CONCURRENCY=5)
        For each URL:
          • GET page (httpx, 15s timeout, follow redirects)
          • Parse HTML with BeautifulSoup (lxml)
          • Find content: <main> → <article> → <body> fallback
          • Strip: nav, footer, header, script, style, noscript, aside
          • Convert cleaned HTML → markdown via markdownify
          • Extract <title> for filename
          • Push progress event per page

OUTPUT: list[ChildPageContent(url, title, markdown_content)]
        Pages that fail to fetch are silently skipped
SSE:    {type: "progress", status: "extracting_content",
         message: "Extracting content 3/15..."}
I/O:    HTTP GET → target website (each child page, concurrent)
```

## Step 5: Assemble Markdown — `services/generator.py`

```
INPUT:  structured_data: dict  (from Step 3)
        child_pages: list[ChildPageContent] | None  (from Step 4, or None)
        site_url: str | None  (original URL, only when child_pages exist)
                 │
                 ▼
        ┌────────┴────────────────┐
        ▼                         ▼
   parent_only mode          full mode
   (child_pages=None)        (child_pages provided)
        │                         │
        ▼                         ▼
   Links use original        Build URL → .md URL lookup:
   page URLs                   slugify(title) → {base_url}/{slug}.md
                                e.g. https://example.com/getting-started.md
                              Links use .md URLs for fetched pages,
                              original URLs for pages that failed to fetch
        │                         │
        └────────┬────────────────┘
                 ▼
        Build markdown string:
          # {site_name}
          > {summary}
          {context}
          ## {section.name}
          - [title](url_or_md_url): description
          ...

OUTPUT: str  — valid llms.txt markdown
I/O:    None (pure transformation)

NOTE:   slugify() is shared between generator.py and the zip endpoint
        to ensure .md filenames match in both the llms.txt links and
        the downloadable zip archive.
```

## Step 6: Complete & Stream

```
INPUT:  markdown: str  (from Step 5)
        child_pages: list[ChildPageContent]  (from Step 4, may be empty)
                 │
                 ▼
        • job["status"] = "completed"
        • job["markdown"] = markdown
        • job["child_pages"] = child_pages  (stored for zip download)
        • Queue.put({type: "complete", markdown: ..., has_child_pages: bool})
        • TODO: persist to Supabase

OUTPUT: SSE event → client receives final markdown + child pages flag
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

## Child Pages Zip Download — `GET /api/generate/{job_id}/child-pages.zip`

```
CONDITION: job must have child_pages (full mode completed)

INPUT:  job_id from URL path
                 │
                 ▼
        Read child_pages from in-memory job store
        Build zip in-memory (io.BytesIO + zipfile):
          For each ChildPageContent:
            • slugify(title) → filename (deduplicated)
            • Write {slug}.md with markdown_content
        Return as StreamingResponse (application/zip)

OUTPUT: ZIP archive containing individual .md files
I/O:    None (reads from in-memory job store)
```

---

## File → Responsibility Map

| File | Role |
|------|------|
| `app/main.py` | FastAPI app init, CORS, request logging middleware |
| `app/config.py` | Pydantic `BaseSettings` — all env vars |
| `app/models.py` | Pydantic models: `GenerateRequest`, `GenerationMode`, `PageMeta`, `ChildPageContent`, `ValidationIssue`, etc. |
| `app/routers/generate.py` | `/api/generate`, `/api/generate/{id}/stream`, `/api/generate/{id}/child-pages.zip`, `/api/reprompt` |
| `app/routers/validate.py` | `/api/validate` |
| `app/services/pipeline.py` | Orchestrator — calls Steps 1→6, manages Queue events, mode-aware |
| `app/services/crawler.py` | Step 1 — sitemap + BFS URL discovery |
| `app/services/extractor.py` | Step 2 — HTML metadata extraction |
| `app/services/content_fetcher.py` | Step 4 — concurrent HTML fetch + markdownify conversion (full mode) |
| `app/services/llm/base.py` | Abstract `LLMProvider` (categorize + reprompt) |
| `app/services/llm/factory.py` | Returns Anthropic or OpenAI provider from config |
| `app/services/llm/anthropic.py` | Anthropic API calls |
| `app/services/llm/openai.py` | OpenAI API calls |
| `app/services/generator.py` | Step 5 — dict → markdown assembly, link rewriting, `slugify()` |
| `app/services/validator.py` | Markdown spec compliance checker |
| `app/prompts/categorize.py` | System + user prompts for categorization |
| `app/prompts/reprompt.py` | System + user prompts for reprompting |
| `app/prompts/summarize.py` | Prompt templates for summarization (stub) |
| `app/testing/mock_llm.py` | Fixture data (bypasses LLM when `MOCK_LLM=true`) |
| `app/db/client.py` | Supabase client stub (`NotImplementedError`) |
| `app/db/jobs.py` | Job persistence stubs (TODO) |

## All External I/O Summary

| Target | Protocol | Where | Purpose |
|--------|----------|-------|---------|
| Target website | HTTP GET | `crawler.py`, `extractor.py` | Sitemap, pages, metadata |
| Target website | HTTP GET | `content_fetcher.py` | Child page HTML (full mode, concurrent) |
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
| `CONTENT_FETCH_CONCURRENCY` | `5` | Max concurrent child page fetches (full mode) |
| `MOCK_LLM` | `True` | Skip real LLM, use fixtures |
| `FRONTEND_URL` | `"http://localhost:5173"` | CORS allowed origin |

## Models

| Model | Fields | Usage |
|-------|--------|-------|
| `GenerationMode` | `PARENT_ONLY`, `FULL` | Enum — controls child page fetching |
| `JobStatus` | `PENDING`, `CRAWLING`, `EXTRACTING_CONTENT`, `PROCESSING`, `COMPLETED`, `ERROR` | Enum — SSE status values |
| `GenerateRequest` | `url`, `client_info?`, `mode` | POST /api/generate body |
| `ChildPageContent` | `url`, `title`, `markdown_content` | Fetched child page data |
| `PageMeta` | `url`, `title`, `description`, `h1?`, `uuid?`, `parent_uuid?` | Extracted page metadata |

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
- Child page fetch failure (full mode) → logged warning, page skipped, link keeps original URL
