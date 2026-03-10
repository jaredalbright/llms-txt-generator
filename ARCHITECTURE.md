# Architecture & Design Decisions

## 1. Executive Summary

**llms.txt Generator** is a web application that produces [llms.txt](https://llmstxt.org/) files — a proposed standard for providing LLM-readable summaries of websites. Given a URL, the tool crawls the site, extracts page metadata, uses an LLM to intelligently categorize and describe pages, and assembles spec-compliant markdown output. The result is a structured document that helps AI assistants understand what a site offers without processing every page.

This matters because as LLMs become the primary interface through which users discover and interact with web content, sites need a machine-readable "front door." llms.txt is to LLMs what robots.txt is to search engines.

**Tech stack:**
- **Backend:** Python 3.14, FastAPI, httpx, BeautifulSoup4, Anthropic/OpenAI SDKs
- **Frontend:** React 19, Vite 6, Tailwind CSS v4, TypeScript
- **Infra:** Vercel (frontend), uvicorn (backend), in-memory storage (Supabase stubbed)

---

## 2. System Architecture Overview

### Data Flow

```
User enters URL
       │
       ▼
┌─────────────┐   POST /api/generate   ┌──────────────────┐
│   Frontend   │ ─────────────────────▶ │   FastAPI Router  │
│  (React 19)  │                        │                   │
│              │   SSE /stream          │  Creates Job +    │
│              │ ◀───────────────────── │  asyncio.Queue    │
└─────────────┘                        └────────┬─────────┘
       │                                        │
       │  EventSource                  asyncio.create_task()
       │  consumes queue                        │
       │                                        ▼
       │                               ┌──────────────────┐
       │                               │   Pipeline DAG    │
       │                               │                   │
       │                               │  crawl ──▶ metadata ─┐
       │                               │                      ├▶ categorize ──▶ fetch ──▶ summarize ──▶ assemble
       │                               │  fetch_homepage ─────┘
       ▼                               └──────────────────┘
┌─────────────┐
│   Editor +   │
│   Preview    │
│              │
│  Export:     │
│  .txt / .zip │
│  / clipboard │
└─────────────┘
```

### Monorepo Layout

```
llms-txt-generator/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # pydantic-settings (Settings class)
│   │   ├── routers/
│   │   │   ├── generate.py      # /generate, /stream, /download.zip
│   │   │   └── validate.py      # /validate
│   │   ├── services/
│   │   │   ├── pipeline/        # DAG engine + 7 node implementations
│   │   │   ├── llm/             # ABC + Anthropic/OpenAI providers
│   │   │   ├── http.py          # Async HTTP fetching with concurrency
│   │   │   ├── html.py          # BeautifulSoup parsing, markdown conversion
│   │   │   ├── url_utils.py     # Normalization, scoring, junk filtering
│   │   │   ├── errors.py        # Error sanitization
│   │   │   ├── progress.py      # StepProgressReporter
│   │   │   ├── generator.py     # Assembly logic (base, md, llms-ctx)
│   │   │   └── validator.py     # llms.txt spec validation
│   │   ├── db/                  # In-memory stores + LRU CacheManager
│   │   ├── models/              # Pydantic models (Job, Generation, PageMeta)
│   │   ├── prompts/             # LLM prompt templates
│   │   └── testing/             # MockLLMProvider for dev
│   └── tests/
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/          # URLInput, PipelineProgress, Editor, etc.
│       ├── hooks/               # useJob, useSSE, useSessionState
│       ├── lib/                 # API client, markdown rendering
│       └── types/
└── ARCHITECTURE.md
```

### API Surface

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/generate` | Start generation job; returns `job_id` (or cached result) |
| `GET` | `/api/generate/{id}/stream` | SSE endpoint for real-time pipeline progress |
| `POST` | `/api/generate/{id}/download.zip` | Download full archive (base/, md/, llms-ctx.txt) |
| `POST` | `/api/validate` | Validate llms.txt markdown against the spec |

---

## 3. Backend Deep Dive

### 3a. DAG-Based Pipeline Engine

The generation pipeline is modeled as a directed acyclic graph rather than a linear sequence. This is implemented in `backend/app/services/pipeline/dag.py` using Python's `graphlib.TopologicalSorter`.

**Why a DAG over a linear pipeline?**
- `crawl` and `fetch_homepage` have no dependency on each other — they can run in parallel, saving ~2-5 seconds on a typical site
- The DAG structure is extensible: adding a new node (e.g., a "detect language" step) means adding one entry with `depends_on` — no reordering of a linear list
- `TopologicalSorter` handles cycle detection for free

**DAG structure:**

```
crawl ──────────────▶ metadata ──┐
                                  ├──▶ categorize ──▶ fetch_content ──▶ summarize ──▶ assemble
fetch_homepage ──────────────────┘
```

**7 pipeline nodes** (defined in `backend/app/services/pipeline/nodes.py`):

| Node | ID | Depends On | Purpose |
|------|----|------------|---------|
| `CrawlNode` | `crawl` | — | Discover pages via sitemap + BFS |
| `FetchHomepageNode` | `fetch_homepage` | — | Fetch and convert homepage to markdown |
| `ExtractMetadataNode` | `metadata` | `crawl` | Extract title/description from discovered pages |
| `CategorizeNode` | `ai_categorize` | `metadata`, `fetch_homepage` | LLM categorizes pages into sections |
| `FetchChildrenNode` | `fetch_content` | `ai_categorize` | Fetch full content of categorized pages |
| `SummarizeNode` | `summarize` | `fetch_content` | Build llms-ctx + LLM refines descriptions |
| `AssembleNode` | `assemble` | `summarize` | Build final base/md/llms-ctx output files |

**Execution model** (`PipelineDAG.execute`):
1. `TopologicalSorter.prepare()` computes the execution order
2. `get_ready()` returns all nodes whose dependencies are satisfied
3. Ready nodes are dispatched with `asyncio.gather()` for parallel execution
4. On completion, `sorter.done(name)` unlocks dependents
5. If any node raises, the exception propagates and the pipeline fails

**Progress reporting:** Each node receives a `StepProgressReporter` wrapping the job's `asyncio.Queue`. Reporters emit three event types:
- `started(message)` — node begins
- `log(detail, message)` — incremental progress (fetched URL, AI chunk, etc.)
- `completed(summary)` — node finished with a summary line

### 3b. Intelligent Web Crawling

The `CrawlNode` implements a three-phase discovery strategy designed to find the most important pages without doing an exhaustive crawl:

**Phase 1: Sitemap**
- Fetches `/sitemap.xml` and parses with `xml.etree.ElementTree`
- All sitemap URLs are registered with `source="sitemap"` at depth 0

**Phase 2: Homepage HTML**
- Fetches the homepage, caches the HTML in `generation._html_cache`
- Extracts two link sets: `nav_links` (from `<nav>` elements) and `body_links` (all `<a>` tags)
- Nav links get `source="nav"` (highest weight), body links get `source="body"`

**Phase 3: BFS Level 1**
- Takes the top N unfetched level-0 URLs (sorted by current score, capped by `bfs_max_level1_urls=20`)
- Fetches them concurrently, caches HTML, and extracts child links at depth 1
- This single BFS hop discovers linked-but-not-sitemapped pages (common for blogs, docs)

**URL scoring heuristic** (`backend/app/services/url_utils.py:score_url`):

```
score = source_weight + depth_score + inlink_bonus - path_penalty
```

- **Source weight:** nav (3.0) > sitemap (2.0) > body (1.0)
- **Depth score:** `1.0 / (1 + depth)` — shallower pages rank higher
- **Inlink bonus:** `min(inlink_count, 5) * 0.2` — pages linked from multiple places are more important
- **Path penalty:** `0.1 * max(segments - 1, 0)` — deeply nested URLs (`/a/b/c/d`) are penalized

After scoring, `rank_and_cap()` sorts descending and takes the top `max_pages` (default 50). The homepage is always included regardless of score.

**Junk URL filtering** (`JUNK_PATTERNS`): 18 compiled regex patterns exclude login, admin, search, cart, feed, wp-admin, file extensions (.pdf, .json, .png, etc.), and other non-content URLs.

**HTML cache reuse:** The `Generation` object carries an `_html_cache: dict[str, str]` that's populated during crawl and reused by downstream nodes (`ExtractMetadataNode`, `FetchHomepageNode`, `FetchChildrenNode`). This avoids re-fetching pages that were already loaded during crawl — a significant optimization for sites with 30-50 pages.

**Concurrency control:** `fetch_urls_concurrent()` in `backend/app/services/http.py` uses an `asyncio.Semaphore(concurrency)` (default 5) to limit parallel outbound connections. A shared `httpx.AsyncClient` is reused across all fetches within a batch.

### 3c. LLM Provider Abstraction

The LLM integration follows an ABC + Factory pattern:

```
LLMProvider (ABC)              ← backend/app/services/llm/base.py
├── AnthropicProvider          ← backend/app/services/llm/anthropic.py
└── OpenAIProvider             ← backend/app/services/llm/openai.py

get_llm_provider() → LLMProvider   ← backend/app/services/llm/factory.py
```

**Abstract interface** — two methods:
- `categorize_pages(site_url, pages, *, homepage_markdown, url_metadata, ...)` → structured JSON with site_name, description, sections
- `summarize(llms_ctx, site_url, current_structured_data, ...)` → improved structured JSON with better descriptions

**Anthropic-specific: tool-use for large homepages**

When the homepage markdown exceeds `homepage_content_threshold` (10,000 chars), `AnthropicProvider` switches to tool-use mode:
- A `search_homepage` tool is defined, allowing the LLM to search specific sections of the homepage content
- The LLM can make up to 5 tool-use rounds, each time querying the homepage with a keyword
- `search_homepage_content()` returns relevant sections matching the query
- This avoids truncating a large homepage and lets the LLM selectively explore what it needs

**OpenAI fallback:** `OpenAIProvider` doesn't support tool-use for this flow. Instead, it truncates the homepage to the threshold length and appends `[... truncated ...]`.

**Streaming with progress reporting:**

Both providers implement `_stream_to_text()` which:
1. Opens a streaming API call
2. Accumulates text chunks
3. Emits detail lines to the `StepProgressReporter` when either 200 characters or 8 seconds have elapsed (whichever comes first)
4. This powers the real-time "AI is thinking..." typewriter effect in the frontend

**Conditional imports:** `backend/app/services/errors.py` wraps `import anthropic` and `import openai` in try/except blocks so neither SDK is a hard dependency — you can run with only one installed.

**Retry and timeout configuration:**
- Anthropic: `max_retries=2`, custom timeout (5s connect, 300s read/write/pool)
- Both providers: `max_tokens=4096` per LLM call
- Pipeline-level: `asyncio.wait_for(timeout=settings.job_timeout)` (default 300s) prevents unbounded runs

### 3d. Real-Time Streaming (SSE)

**Architecture:**

```
Pipeline Node
    │
    ▼
StepProgressReporter.log()
    │
    ▼
asyncio.Queue.put({type: "progress", step, detail, ...})
    │
    ▼
EventSourceResponse (sse-starlette)
    │
    ▼
Browser EventSource API
```

**Per-job Queue:** An `asyncio.Queue` is created when the job is created (in `create_job()`) and passed to both the pipeline task and the SSE endpoint. This decouples production (pipeline writes events) from consumption (SSE reads events).

**Event types:**

| Event | When | Payload |
|-------|------|---------|
| `progress` | Node started, in-progress, or completed | `{step, step_state, message, detail, summary}` |
| `complete` | Pipeline finished successfully | `{markdown, job_id}` |
| `error` | Pipeline failed | `{message}` (sanitized) |

**Why SSE over WebSocket:**
- **Unidirectional:** The client never sends data back through this channel — it's purely server→client
- **Simpler:** No upgrade handshake, no ping/pong, no reconnection logic on the server
- **Auto-reconnect:** `EventSource` automatically reconnects on connection loss (the frontend handles `readyState === CLOSED`)
- **HTTP/2 compatible:** Multiplexes over a single TCP connection
- **Keep-alive:** `EventSourceResponse(ping=15)` sends pings every 15 seconds to prevent proxy timeouts

### 3e. Caching & Storage

**CacheManager** (`backend/app/db/cache.py`):

A unified LRU cache manager coordinates both the Job and Generation in-memory stores:

```
CacheManager
├── _order: OrderedDict[job_id → normalized_url]   (LRU ordering)
├── _url_index: dict[normalized_url → job_id]       (reverse lookup)
├── _active_ids: set[job_id]                         (non-evictable)
└── _stores: list[Removable]                         (registered stores)
```

**Key behaviors:**
- `track(job_id, url)` — registers a new job as active and non-evictable
- `touch(job_id)` — bumps to most-recently-used on any access
- `mark_finished(job_id)` — removes from active set, triggers eviction check
- `lookup_url(url)` — URL-normalized reverse lookup for cache hits
- `_maybe_evict()` — evicts oldest finished entries when over `max_entries` (default 100)

**Active jobs are never evicted.** Only completed or errored jobs can be removed. This prevents in-flight pipelines from losing their state.

**Cache-hit flow** (in `POST /api/generate`):
1. Normalize the request URL
2. Look up in `_url_index` → get `job_id`
3. Verify job exists, is completed, and has markdown
4. Return `GenerateResponse(cached=True, markdown=...)` immediately
5. Frontend shows a modal: "Load previous result" vs "Generate new"
6. If "Generate new": re-submit with `force=true` to bypass cache

**URL normalization** (`url_utils.normalize_url`): lowercase scheme/netloc, strip fragments and tracking params (utm_*, fbclid, gclid, etc.), collapse double slashes, remove trailing slash. This ensures `https://Example.com/path/` and `https://example.com/path?utm_source=x` map to the same cache entry.

### 3f. Error Sanitization & Security

**`sanitize_error()`** (`backend/app/services/errors.py`) maps exception types to safe user-facing messages:

| Exception Type | User Message |
|----------------|-------------|
| `anthropic.AuthenticationError` / `openai.AuthenticationError` | "LLM service authentication failed. Check API key configuration." |
| `asyncio.TimeoutError` | "Generation timed out. The site may be too large or the AI service is slow." |
| `httpx.HTTPError` | "Failed to fetch website content. The site may be unreachable." |
| `ValueError` | "AI returned an unexpected response. Please try again." |
| Everything else | "An unexpected error occurred. Please try again." |

**What's never leaked:**
- API key prefixes or full keys
- File paths or stack traces
- Internal class names or module paths
- Raw LLM response text (logged server-side at DEBUG level only)

**HTTP status codes:** The router uses proper status codes:
- `404` for unknown job IDs
- `409` for attempting to download from an incomplete job
- Not `200` with an error body

**Job-level timeout:** `asyncio.wait_for(dag.execute(...), timeout=settings.job_timeout)` (default 300s) prevents any pipeline from running indefinitely. On timeout, the caught `asyncio.TimeoutError` is sanitized and sent as an SSE error event.

---

## 4. Frontend Product Features

### 4a. Real-Time Pipeline Visualization

The `PipelineProgress` component (`frontend/src/components/PipelineProgress.tsx`) renders a vertical step list driven by SSE events:

**State machine per step:** `pending → active → completed`
- **Pending:** Gray circle, dimmed label
- **Active:** Pulsing blue circle, thinking dots animation, live detail log
- **Completed:** Green checkmark, summary text, collapsible detail log

**Typewriter effect:** The `useTypewriter` hook animates text appearing character-by-character:
- Dynamic speed: each batch finishes in ~400ms, clamped between 1-40ms/char
- Uses `requestAnimationFrame` for smooth 60fps animation
- `TypewriterBlock` concatenates all detail strings for AI steps (streaming LLM output), `TypewriterLine` animates individual log lines for non-AI steps

**Auto-scroll:** Detail log containers auto-scroll to bottom as new content arrives.

**Auto-collapse:** When a step transitions from active to completed, the detail body auto-collapses after 400ms. Completed steps can be re-expanded by clicking.

### 4b. Markdown Editor + Live Preview

`EditorPreview` (`frontend/src/components/EditorPreview.tsx`) provides a split-pane interface:

- **Left pane:** `<textarea>` editor with JetBrains Mono font, read-only when collapsed
- **Right pane:** `Preview` component renders markdown as formatted HTML using `@tailwindcss/typography`
- **Collapsed state:** Max height 300px with a gradient fade and "Click to expand" hover label
- **Expanded state:** Full height with "Collapse" button at bottom

**Live spec validation** (debounced 2s):
- `useJob` hook watches `markdown` changes
- After 2s of no edits, calls `POST /api/validate`
- Displays line-number issues below the editor: "Line 5: Missing description"
- Export button is disabled when validation fails or is in-progress

**Export dropdown** (`ExportDropdown`):
- Copy to clipboard (with "Copied!" feedback)
- Download as `.txt` (client-side Blob)
- Download as `.zip` (server-side via `POST /api/generate/{id}/download.zip`)

The `.zip` archive contains:
```
llms-txt.zip
├── base/llms.txt       # Original URLs
├── md/llms.txt         # URLs replaced with .md file references
├── md/*.md             # Individual page content files
└── llms-ctx.txt        # Expanded context with inline page content
```

### 4c. Session Persistence

`useSessionState` (`frontend/src/hooks/useSessionState.ts`) wraps `useState` with `sessionStorage` persistence:
- All job state (`jobId`, `markdown`, `status`, `url`, `clientInfo`, `promptsContext`) survives page refresh
- Falls back to default value on parse error or missing key

**URL path sync:** `useJob` keeps the browser URL in sync with the job:
- `setJobId("abc-123")` → `window.history.pushState(null, '', '/abc-123')`
- `reset()` → `pushState(null, '', '/')`
- `popstate` listener handles browser back/forward navigation
- On mount, `replaceState` corrects the URL to match session state

**Cache-hit modal:** When `POST /api/generate` returns `cached=true`:
1. The cached markdown and job_id are stored in `cacheHit` state
2. A modal presents two options: "Load previous result" or "Generate new"
3. "Generate new" re-submits with `force=true` to bypass the cache
4. Escape key dismisses and triggers generate new

### 4d. Styling & Design System

**Tailwind CSS v4** uses the `@theme` directive in CSS (not `tailwind.config.ts`):

**Custom design tokens:**
- `profound-blue`: `#376CFF` — primary action color
- `profound-surface`, `profound-border`, `profound-muted` — surface/border/text tokens
- Fonts: Inter (body), JetBrains Mono (code/editor)

**Component patterns:**
- Cards: `bg-white border border-profound-border rounded-xl`
- Buttons: `bg-profound-blue text-white rounded-lg` (primary), `border border-profound-border` (secondary)
- Animations: `animate-pulse` for active states, `animate-bounce` for thinking dots, CSS grid transitions for expandable sections

---

## 5. Key Design Decisions & Trade-offs

### In-Memory Storage
**Chosen for:** Zero infrastructure, instant startup, no DB migrations for MVP.
**Trade-off:** All data lost on process restart. LRU eviction (100 entries) means old results disappear under load. No multi-process sharing.
**Mitigation:** Supabase schema is stubbed in `db/repository.py` and `db/generation_store.py` — the swap is a one-file change per store.

### SSE over WebSocket
**Chosen for:** Simpler server implementation (no connection upgrade, no bidirectional framing). `EventSource` handles reconnection natively. HTTP/2 compatible.
**Trade-off:** No client→server channel through the stream. The client must use separate HTTP calls for actions (regenerate, download).
**Why it works here:** The progress stream is purely server→client. The only client→server interactions (submit URL, download zip) are standard REST calls.

### DAG over Linear Pipeline
**Chosen for:** `crawl` and `fetch_homepage` run in parallel (~2-5s saved). Adding nodes doesn't require reordering.
**Trade-off:** Slightly more complex orchestration code. `graphlib.TopologicalSorter` is stdlib (Python 3.9+), so no extra dependency.
**Extensibility:** A future "detect language" node could depend only on `crawl` and run in parallel with `metadata`.

### Tool-Use for Large Homepages (Anthropic-specific)
**Chosen for:** Homepages over 10K chars would consume too much context if sent inline. Tool-use lets the LLM selectively query sections.
**Trade-off:** Only works with Anthropic's API. OpenAI falls back to truncation. Up to 5 extra API round-trips.
**Why it matters:** Marketing homepages routinely exceed 20K chars. Truncation loses the footer/nav/pricing sections that are critical for accurate categorization.

### Monorepo
**Chosen for:** Single repo for coordinated deploys, shared understanding, simpler CI.
**Trade-off:** Frontend and backend have different toolchains (npm vs pip). No shared types (Python ↔ TypeScript) yet.

### No Client-Side Router
**Chosen for:** The app has a single screen with three states (input, progress, editor). React Router adds complexity for one-screen apps.
**How URL sync works:** `useJob` manually calls `history.pushState`/`replaceState` and listens for `popstate`. The URL path is either `/` or `/{job_id}`.

---

## 6. Productionization Roadmap

### 6a. Storage & Persistence

**Current:** `InMemoryJobCache` and `InMemoryGenerationCache` with LRU eviction.

**Production:**
- **PostgreSQL via Supabase** for durable job/generation storage (repository interfaces already defined)
- **Redis** for the LRU cache layer and job queue broker
- **S3/R2** for generated `.zip` artifacts (currently built on-the-fly per download)

**Migration path:** The `JobRepository` and `GenerationStore` are abstract interfaces. Swapping in a Supabase implementation means implementing `create()`, `get()`, `update()` against the Supabase client — the pipeline and router code doesn't change.

### 6b. Scalability

**Current:** Single-process, all jobs share one event loop. `asyncio.create_task()` launches pipeline runs concurrently within the same process.

**Production:**
- **Task queue** (Celery or Dramatiq with Redis broker) to offload pipeline execution
- **Stateless API servers** that accept requests and enqueue tasks
- **Horizontal scaling:** Multiple API server instances behind a load balancer; workers scale independently based on queue depth
- **Rate limiting:** `slowapi` or API gateway rules per IP/API key to prevent abuse
- **Estimated capacity:** Current single-process handles ~10 concurrent jobs (limited by LLM API latency, not CPU). Task queue removes this ceiling.

### 6c. Observability

**Current:** `logging.basicConfig` with formatted output to stdout. Noisy third-party loggers (httpx, httpcore) are quieted.

**Production:**
- **Structured logging** (`structlog`) with JSON output and correlation IDs per job
- **Distributed tracing** (OpenTelemetry) across pipeline nodes — each node becomes a span, enabling flame-chart visualization of job execution
- **Metrics:** Job duration, LLM latency (p50/p95/p99), crawl success rate, cache hit ratio, pages discovered per job
- **Error alerting:** Sentry for exception tracking with context (job_id, URL, pipeline step)

### 6d. Security Hardening

**Current:** CORS restricted to `settings.frontend_url`. Error sanitization prevents leaking internals. Junk URL filtering prevents crawling login/admin pages.

**Production:**
- **BYOA (Bring Your Own API Key):** Encrypt keys at rest, never log them, scope to session lifetime, clear on completion
- **CORS tightening:** Exact origin match (already done), validate `Origin` header
- **Input validation:** URL allowlist/blocklist (no internal IPs, no `file://`), max request body size
- **Rate limiting:** Per-IP and per-API-key limits
- **Content Security Policy:** Strict CSP headers on the frontend

### 6e. Reliability

**Current:** `max_retries=2` on Anthropic client. `asyncio.wait_for` with 300s timeout. Basic error catching with sanitized user messages.

**Production:**
- **Retry with exponential backoff** for all LLM calls (extend beyond Anthropic's built-in retries)
- **Circuit breaker pattern** for external services (LLM APIs, target websites) — fail fast when a service is down
- **Graceful shutdown:** Drain in-flight jobs before process exit (SIGTERM handler)
- **Health check enhancement:** Add readiness probe that verifies LLM API connectivity
- **Dead letter queue:** Failed jobs that exceed retry budget get logged for manual review

### 6f. Performance

**Current:** Frontend on Vercel CDN. `httpx.AsyncClient` created per `fetch_url()` call (not pooled). HTML cache avoids redundant fetches within a single job.

**Production:**
- **Connection pooling:** Shared `httpx.AsyncClient` with connection pool (currently creates a new client per `fetch_url` call, but `fetch_urls_concurrent` already shares one client per batch)
- **Precomputed sitemap cache:** TTL-based cache for sitemap.xml across jobs for the same domain
- **Streaming .zip response:** Currently builds the full zip in memory; for large sites, stream chunks
- **CDN for frontend:** Already handled by Vercel
- **LLM response caching:** Cache categorization results by URL + page list hash for identical re-requests

### 6g. Testing

**Current test suite:**
- `test_generator.py` — Assembly logic (base markdown, md markdown, llms-ctx)
- `test_validator.py` — llms.txt spec validation
- `test_url_utils.py` — URL normalization, scoring, junk filtering
- `test_cache.py` — CacheManager LRU behavior, eviction, URL lookup
- `test_errors.py` — Error sanitization mapping
- `MockLLMProvider` — Returns fixture data when `MOCK_LLM=true`

**Production additions:**
- **Integration tests:** Full pipeline runs with `MockLLMProvider`, verifying SSE event sequence
- **E2E tests:** Playwright for the complete user flow (enter URL → progress → editor → export)
- **Load testing:** Locust to verify concurrent job handling and identify bottlenecks
- **Contract tests:** Validate LLM response schemas match expected structured data format
- **CI/CD:** GitHub Actions: lint (ruff) → type check (pyright) → unit tests → build frontend → deploy

---

## 7. What I'd Do Differently at Scale

**Event-driven architecture:** Replace the in-process DAG with event-driven execution. Each pipeline step publishes a completion event that triggers the next step. Benefits: each step can scale independently, failed steps can be retried in isolation, and the system naturally supports distributed execution.

**Separate crawler microservice:** Crawling has a fundamentally different scaling profile than LLM calls. Crawling is I/O-bound and benefits from many concurrent connections; LLM calls are rate-limited by the provider. A dedicated crawler service with its own connection pool and rate limits would decouple these concerns.

**LLM calls behind a queue with backpressure:** Instead of calling the LLM directly from pipeline nodes, enqueue LLM requests with priority lanes. Batch categorization requests when possible. Apply backpressure when the LLM provider is slow or rate-limited. This prevents one slow LLM response from blocking the entire pipeline.

**Webhook callbacks instead of long-lived SSE:** For production workloads, long-lived SSE connections tie up server resources. A webhook-based notification system where the client registers a callback URL would scale better. The frontend could poll or use short-lived SSE connections with `Last-Event-ID` for resumption.

**Multi-tenant with org-level API keys:** Instead of a single server-side API key, support organization accounts with their own API keys, usage tracking, and billing. The BYOA feature is a step in this direction, but full multi-tenancy would require proper auth, quota management, and usage dashboards.
