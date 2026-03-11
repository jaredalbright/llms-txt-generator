# Backend Workflow

## Pipeline Overview

The pipeline is a DAG (directed acyclic graph) of nodes, executed by `PipelineDAG` using `graphlib.TopologicalSorter`. Nodes at the same dependency level run concurrently.

```
POST /api/generate(url, client_info?, prompts_context?, force?)
  │
  ├─ 1. Crawl           → Discover URLs (sitemap + homepage links + BFS level-1)
  │                        Filter junk URLs, score, rank, and cap at MAX_PAGES
  ├─ 2. Extract Metadata → Fetch + extract title/description/h1 (concurrent, uses HTML cache)
  ├─ 2b. Fetch Homepage  → Fetch homepage HTML → convert to markdown (runs parallel with crawl→extract)
  ├─ 3. LLM Categorize   → Send pages + homepage + url metadata to LLM → structured JSON
  ├─ 4. Fetch Content    → Fetch + convert all categorized pages to markdown (concurrent, uses HTML cache)
  ├─ 5. Summarize        → Build llms-ctx.txt, then run second LLM pass to refine descriptions
  └─ 6. Assemble         → Build base llms.txt + md llms.txt → SSE complete
```

**DAG structure:**
```
crawl ──────────> extract_metadata ──┐
                                      ├──> ai_categorize ──> fetch_content ──> summarize ──> assemble
fetch_homepage ──────────────────────┘
```

`crawl` and `fetch_homepage` run in parallel. `extract_metadata` waits for `crawl`. `ai_categorize` waits for both `extract_metadata` and `fetch_homepage`.

All orchestration lives in `services/pipeline/__init__.py`, which builds the DAG and calls `dag.execute()` inside an `asyncio.wait_for` with `JOB_TIMEOUT`. Progress events are pushed to an `asyncio.Queue` consumed by the SSE stream.

---

## Step 1: URL Discovery (`services/pipeline/nodes.py` → `CrawlNode`)

```
CrawlNode.execute()
  │
  ├─ 1. Fetch /sitemap.xml (10s timeout)
  │     └─ Parse XML <loc> tags, register each as source="sitemap", depth=0
  │
  ├─ 2. Fetch homepage HTML (cache it for later reuse)
  │     ├─ Extract <nav> links → register as source="nav", depth=0
  │     └─ Extract all <a href> links → register as source="body", depth=0
  │
  ├─ 3. BFS Level 1
  │     ├─ Take unfetched depth-0 URLs, sorted by score descending
  │     ├─ Fetch top BFS_MAX_LEVEL1_URLS (default 20) concurrently
  │     ├─ Cache HTML for each
  │     └─ Extract links from each → register as source="body", depth=1
  │
  ├─ 4. Filter junk URLs (url_utils.filter_junk_urls)
  │     └─ Removes: /login, /logout, /signup, /register, /auth/, /admin,
  │        /api/ (but NOT /api-reference), /page/N, /tag/, /category/,
  │        /cart, /checkout, /search, /feed, /rss, /wp-admin/, /wp-json/,
  │        file extensions (.xml, .json, .pdf, .zip, images, .css, .js, fonts)
  │
  └─ 5. Rank & cap (url_utils.rank_and_cap)
        ├─ Score each URL: source_weight + depth_score + inlink_bonus - path_penalty
        │   source weights: nav=3.0, sitemap=2.0, body=1.0
        │   depth_score: 1/(1+depth)
        │   inlink_bonus: min(inlinks, 5) * 0.2
        │   path_penalty: 0.1 * max(segments-1, 0)
        ├─ Sort by score descending, take top MAX_PAGES
        └─ Always include homepage regardless of score
```

**URL normalization** (`url_utils.normalize_url`):
- Lowercase scheme + netloc
- Strip fragments
- Strip tracking query params (utm_*, fbclid, gclid, ref, source, mc_*)
- Remove trailing slashes (except root `/`)
- Collapse double slashes in path

**HTML caching:** The crawl node stores raw HTML in `generation._html_cache` keyed by URL. This cache is reused by `ExtractMetadataNode`, `FetchHomepageNode`, and `FetchChildrenNode` to avoid re-fetching pages.

---

## Step 2: Metadata Extraction (`services/pipeline/nodes.py` → `ExtractMetadataNode`)

For each discovered URL, extract:

- `title` from `<title>` tag
- `description` from `<meta name="description">` → fallback `og:description` → fallback first `<p>` with >20 chars (`extract_first_paragraph`)
- `h1` from first `<h1>` tag

**Execution:**
1. Check HTML cache first — process cached pages immediately
2. Fetch uncached pages concurrently via `http.fetch_urls_concurrent` (semaphore at `CONTENT_FETCH_CONCURRENCY`, default 5)
3. Cache fetched HTML for downstream reuse

Returns `list[PageMeta(url, title, description, h1)]`.

---

## Step 2b: Homepage Markdown (`services/pipeline/nodes.py` → `FetchHomepageNode`)

Runs in parallel with crawl → extract. Produces markdown from the homepage for LLM context.

1. Check HTML cache (populated by crawl step)
2. If not cached, fetch the homepage
3. Convert HTML → markdown via `html.html_to_markdown`:
   - Find content: `<main>` → `<article>` → `<body>` fallback
   - Strip: nav, footer, header, script, style, noscript, aside
   - Convert to markdown via `markdownify` (skip images)

Sets `generation.homepage_markdown`.

---

## Step 3: LLM Categorization (`services/pipeline/nodes.py` → `CategorizeNode`)

If `MOCK_LLM=true`: uses `MockLLMProvider.mock_structured_data()` — puts first 10 pages in "Main", rest in "Optional", no real LLM call.

If `MOCK_LLM=false`: calls `llm.categorize_pages()`.

### What the LLM receives

```
┌──────────────────────────────────────────────────────────┐
│ SYSTEM PROMPT (prompts/categorize.py)                     │
│                                                           │
│ • llms.txt spec (format rules)                            │
│ • Tasks: pick site name, write description + details,     │
│   group pages into 2-6 sections, use "Optional" section   │
│ • Guidelines: <15 word descriptions, ~10 main links,      │
│   every page in exactly one section                       │
├───────────────────────────────────────────────────────────┤
│ USER PROMPT (build_categorize_user_prompt)                 │
│                                                           │
│ • Site URL                                                │
│ • client_info (optional user context about the site)      │
│ • prompts_context (optional AI search prompts to          │
│   optimize for — keywords woven into descriptions)        │
│ • Flat list of all pages:                                 │
│     - URL, Title, Description                             │
│     - Source: nav/sitemap/body | Depth: N | Inlinks: N    │
│ • Homepage markdown (inlined or via tool)                 │
└───────────────────────────────────────────────────────────┘
```

### Homepage handling by size

| Homepage size              | Provider  | Mode          | Behavior                                                                    |
| -------------------------- | --------- | ------------- | --------------------------------------------------------------------------- |
| < 10,000 chars             | Both      | **Inline**    | Homepage markdown included directly in user prompt                          |
| ≥ 10,000 chars             | Anthropic | **Tool-use**  | LLM gets `search_homepage(query)` tool, searches by keyword. Max 5 rounds. |
| ≥ 10,000 chars             | OpenAI    | **Truncated** | Homepage truncated to 10,000 chars + `[... truncated ...]`                  |

### LLM output (JSON)

```json
{
  "site_name": "Human Readable Name",
  "description": "One sentence for the blockquote.",
  "details": "Markdown body text with keywords for discoverability.",
  "sections": [
    {
      "name": "Section Name",
      "pages": [
        {"title": "Page Title", "url": "https://...", "description": "What this covers."}
      ]
    }
  ]
}
```

Both Anthropic and OpenAI providers stream the response, emitting partial output as SSE detail events every 200 chars or 8 seconds.

---

## Step 4: Content Fetching (`services/pipeline/nodes.py` → `FetchChildrenNode`)

Fetches every URL from the LLM's structured output and converts to markdown:

1. Check HTML cache first (pages already fetched during crawl/BFS)
2. Fetch uncached pages concurrently (`CONTENT_FETCH_CONCURRENCY`, default 5)
3. For each page: `html.html_to_markdown()` → find main/article/body, strip nav/footer/etc, convert to markdown

Returns `list[ChildPageContent(url, title, markdown_content)]`. Failed pages are silently skipped.

---

## Step 5: Summarize (`services/pipeline/nodes.py` → `SummarizeNode`)

Two-part step:

**Part 1 — Build llms-ctx.txt:**
Assembles `llms-ctx.txt` by inlining fetched page content into `<doc>` XML tags:
```markdown
## Section Name
<doc url="https://..." title="Page Title">
Full markdown content of the page...
</doc>
```
Pages without fetched content fall back to link + description format.

**Part 2 — LLM refinement (conditional):**
Runs when `MOCK_LLM=false` AND `llms_ctx` is non-empty. Calls `llm.summarize()`:
- Sends the current structured JSON + full llms-ctx to the LLM
- Prompt: `prompts/summarize.py`
- LLM returns updated structured JSON with improved:
  - Site description (blockquote)
  - Details paragraph (body text)
  - Per-page descriptions (informed by actual page content)
- Rebuilds llms-ctx with the improved data
- On failure (`ValueError`/`KeyError`), falls back to original data with a warning

---

## Step 6: Assemble (`services/pipeline/nodes.py` → `AssembleNode`)

Builds two final output formats from `structured_data`:

**`assemble_base_markdown()`** → `llms.txt` with original site URLs
```markdown
# Site Name
> One sentence description.
Details paragraph...

## Section Name
- [Page Title](https://original-url.com): Description
```

**`assemble_md_markdown()`** → `llms.txt` with `.md` file URLs
```markdown
## Section Name
- [Page Title](https://site.com/page-title.md): Description
```
Slug generation: title → lowercase, strip special chars, spaces to hyphens, cap at 80 chars. Duplicates get `-1`, `-2` suffixes.

The `llms-ctx.txt` was already built in the Summarize step.

---

## Endpoints

| Method | Path                              | Purpose                                                                                        |
| ------ | --------------------------------- | ---------------------------------------------------------------------------------------------- |
| `GET`  | `/health`                         | Health check                                                                                   |
| `POST` | `/api/generate`                   | Start generation. Body: `{url, client_info?, prompts_context?, force?}`. Returns `{job_id}`.   |
| `GET`  | `/api/generate/{id}/stream`       | SSE stream. Events: `progress`, `complete`, `error`. Ping every 15s.                           |
| `POST` | `/api/generate/{id}/download.zip` | Build ZIP from user-edited markdown. Returns ZIP with base + md + ctx + individual .md files.   |
| `POST` | `/api/validate`                   | Validate markdown against llms.txt spec. Body: `{markdown}`. Returns `{valid, issues[]}`.      |
| `GET`  | `/api/generations/recent`         | List recently completed generations. Query: `?limit=10`.                                       |
| `GET`  | `/api/generations/search`         | Search previous generations by URL. Query: `?url=...&limit=3`.                                 |
| `GET`  | `/api/generations/{id}`           | Get a single generation with its markdown.                                                     |

### Cache behavior on POST /api/generate

When `force` is not set:
1. Check in-memory cache (via `CacheManager.lookup_url` — normalized URL index)
2. If no in-memory hit, check Supabase for previous completed generations
3. If cache hit, return `{job_id, cached: true, markdown}` immediately
4. Frontend shows a cache modal — user can accept cached or force regenerate

---

## SSE Progress Events

Each pipeline node reports progress through `StepProgressReporter`:

```json
{"type": "progress", "step": "crawl", "step_state": "started", "message": "Discovering pages..."}
{"type": "progress", "step": "crawl", "step_state": "progress", "detail": "Sitemap: 34 URLs"}
{"type": "progress", "step": "crawl", "step_state": "completed", "message": "Found 34 pages", "summary": "Found 34 pages"}
{"type": "progress", "step": "metadata", "step_state": "started", ...}
{"type": "progress", "step": "ai_categorize", "step_state": "progress", "detail": "...partial LLM output..."}
{"type": "progress", "step": "summarize", "step_state": "progress", "detail": "Refining descriptions with AI..."}
{"type": "progress", "step": "assemble", "step_state": "completed", ...}
{"type": "complete", "markdown": "# Site Name\n> ...", "job_id": "..."}
```

`step_state` transitions: `started` → `progress` (0..n) → `completed`

---

## File Map

| File                               | Role                                                          |
| ---------------------------------- | ------------------------------------------------------------- |
| `app/main.py`                      | FastAPI app, CORS, logging, storage init (Supabase or memory) |
| `app/config.py`                    | Pydantic `BaseSettings` — all env vars                        |
| `app/models/base.py`               | Request/response models, `PageMeta`, `ChildPageContent`, `Job`|
| `app/models/generation.py`         | `Generation` dataclass — pipeline artifact with all outputs   |
| `app/routers/generate.py`          | POST /generate, GET /stream, POST /download.zip               |
| `app/routers/validate.py`          | POST /validate                                                |
| `app/routers/generations.py`       | GET /generations/recent, /search, /{id}                       |
| `app/services/pipeline/__init__.py` | DAG builder + `run_pipeline()` orchestrator                  |
| `app/services/pipeline/dag.py`     | `PipelineDAG` — topological sort + parallel execution         |
| `app/services/pipeline/node.py`    | `PipelineNode` abstract base class                            |
| `app/services/pipeline/nodes.py`   | All 7 node implementations                                   |
| `app/services/http.py`             | `fetch_url`, `fetch_sitemap_urls`, `fetch_urls_concurrent`    |
| `app/services/html.py`             | HTML parsing: link extraction, metadata, markdown conversion  |
| `app/services/url_utils.py`        | URL normalize, junk filter, scoring, ranking                  |
| `app/services/generator.py`        | Markdown assembly (base, md, ctx) + `slugify()`               |
| `app/services/validator.py`        | llms.txt spec compliance checker                              |
| `app/services/progress.py`         | `StepProgressReporter` — SSE event helper                     |
| `app/services/errors.py`           | `sanitize_error()` — user-safe error messages                 |
| `app/services/llm/base.py`         | Abstract `LLMProvider` (categorize + summarize)               |
| `app/services/llm/factory.py`      | Provider selection from config                                |
| `app/services/llm/anthropic.py`    | Anthropic API (streaming + tool use for large homepages)      |
| `app/services/llm/openai.py`       | OpenAI API (streaming, no tool use)                           |
| `app/services/llm/utils.py`        | `extract_json()`, streaming interval constants                |
| `app/prompts/categorize.py`        | System/user prompts + `search_homepage` tool definition       |
| `app/prompts/summarize.py`         | Summarize system/user prompts                                 |
| `app/db/cache.py`                  | `CacheManager` — LRU cache with URL index + eviction          |
| `app/db/repository.py`             | `JobRepository` ABC + singleton                               |
| `app/db/memory.py`                 | `InMemoryJobCache` — in-memory job store                      |
| `app/db/generation_store.py`       | `GenerationStore` ABC + `InMemoryGenerationCache`             |
| `app/db/supabase_store.py`         | `SupabaseGenerationStore` — Supabase-backed persistence       |
| `app/db/client.py`                 | Lazy Supabase client init                                     |
| `app/testing/mock_llm.py`          | Mock data for `MOCK_LLM=true`                                 |

---

## Configuration

| Var                          | Default                      | Purpose                                    |
| ---------------------------- | ---------------------------- | ------------------------------------------ |
| `LLM_PROVIDER`               | `"anthropic"`                | `"anthropic"` or `"openai"`                |
| `LLM_MODEL`                  | `"claude-sonnet-4-20250514"` | Model for categorization + summarize       |
| `ANTHROPIC_API_KEY`          | `""`                         | Anthropic API key                          |
| `OPENAI_API_KEY`             | `""`                         | OpenAI API key                             |
| `SUPABASE_URL`               | `""`                         | Supabase project URL (empty = in-memory)   |
| `SUPABASE_KEY`               | `""`                         | Supabase anon/service key                  |
| `MAX_PAGES`                  | `50`                         | URL discovery cap after ranking            |
| `CRAWL_TIMEOUT`              | `30`                         | Seconds per page fetch                     |
| `CONTENT_FETCH_CONCURRENCY`  | `5`                          | Concurrent page fetches                    |
| `HOMEPAGE_CONTENT_THRESHOLD` | `10000`                      | Chars before switching to tool-use mode    |
| `BFS_MAX_LEVEL1_URLS`        | `20`                         | Max pages to fetch in BFS level-1          |
| `CACHE_MAX_ENTRIES`          | `100`                        | Max in-memory cache entries before eviction|
| `MOCK_LLM`                   | `true`                       | Skip real LLM calls, return fixture data   |
| `JOB_TIMEOUT`                | `300`                        | Seconds; max duration for entire pipeline  |
| `FRONTEND_URL`               | `http://localhost:5173`      | CORS origin                                |
| `PROFOUND_API_KEY`           | `""`                         | (Reserved)                                 |

---

## Storage Architecture

Two parallel storage systems:

**JobRepository** (`db/repository.py` → `InMemoryJobCache`)
- Holds `Job` objects with `event_queue` for SSE streaming
- Always in-memory (queues can't be persisted)
- Managed by `CacheManager` for LRU eviction

**GenerationStore** (`db/generation_store.py`)
- Holds `Generation` objects with all pipeline outputs
- Two backends:
  - `InMemoryGenerationCache` — default, also managed by `CacheManager`
  - `SupabaseGenerationStore` — used when `SUPABASE_URL` + `SUPABASE_KEY` are set
- `main.py` checks for Supabase at startup and selects the backend

**CacheManager** (`db/cache.py`)
- Unified LRU ordering across both stores
- URL index for cache-hit lookups (normalized URLs)
- Active jobs (pending/in-progress) are never evicted
- Eviction triggers when total entries exceed `CACHE_MAX_ENTRIES`
