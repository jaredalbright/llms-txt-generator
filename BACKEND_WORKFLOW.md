# Backend Workflow

## Pipeline Overview

```
POST /generate(url, client_info?)
  │
  ├─ 1. Crawl         → Discover URLs (sitemap + BFS fallback)
  ├─ 2. Extract        → Fetch metadata (title, description, h1) from each URL
  ├─ 2b. Homepage      → Fetch homepage HTML → convert to markdown
  ├─ 3. LLM Categorize → Send pages + homepage to LLM → structured JSON
  ├─ 4. Fetch Content  → Fetch + convert all categorized pages to markdown
  ├─ 5. Build Context  → Assemble llms-ctx.txt (inlined page content)
  ├─ 6. Summarize      → (disabled) LLM refinement pass using llms-ctx
  └─ 7. Assemble       → Build base llms.txt + md llms.txt → SSE complete
```

All steps run inside `run_pipeline()` in `services/pipeline.py`, orchestrated as a single async task with progress events pushed to an `asyncio.Queue` consumed by the SSE stream.

---

## How URLs Are Picked (The Critical Path)

This is the most impactful part of the pipeline. Every downstream step depends on the quality and relevance of the URLs discovered here.

### Step 1: URL Discovery (`services/crawler.py`)

```
crawl_site(url)
  │
  ├─ Try /sitemap.xml (10s timeout)
  │   └─ Parse XML <loc> tags
  │
  ├─ If sitemap returned < 5 URLs:
  │   └─ Fallback: extract <a href> from homepage (single-page, not true BFS)
  │
  ├─ Always include the homepage URL
  ├─ Filter to same-domain only (netloc match)
  ├─ Strip fragments and query params
  └─ Cap at MAX_PAGES (default 50)
```

**Current behavior:**

- Sitemap is the primary source. If a site has a good sitemap, this works well.
- If the sitemap has fewer than 5 URLs (or is missing), falls back to scraping `<a>` tags from the homepage only.
- The fallback does NOT implement true BFS despite the `max_depth=2` parameter — it only reads one page. The TODO at line 79 of `crawler.py` acknowledges this.
- No filtering of junk URLs (login pages, API endpoints, admin panels, asset paths, etc.)
- No prioritization — the first 50 URLs found (in set iteration order) are used.

**Problems with current URL selection:**

1. **No URL filtering.** Sitemap dumps include everything: `/login`, `/api/v1/docs`, `/admin`, `/terms-of-service`, old blog posts, paginated archives (`/blog/page/3`), etc. These all get sent to the LLM and waste tokens/attention.
2. **No ranking or scoring.** A critical product documentation page and a 3-year-old changelog entry are treated identically. The LLM has to figure out importance from titles alone.
3. **Incomplete fallback.** The BFS crawler only reads the homepage, so sites without sitemaps get very few URLs. A true 2-hop crawl would find significantly more pages.
4. **Arbitrary threshold.** The `< 5` sitemap URL check is a magic number. A site could have exactly 5 low-quality sitemap URLs (all blog posts) and skip the fallback entirely.
5. **No deduplication of near-duplicates.** `/docs/getting-started` and `/docs/getting-started/` are treated as different URLs. Query params are stripped, but trailing slashes are only handled for the homepage.

### Optimization Opportunities for URL Selection

**Pre-filter junk URLs before they reach the LLM:**

```python
EXCLUDE_PATTERNS = [
    r'/api/',  r'/admin/',  r'/auth/',  r'/login',  r'/logout',
    r'/signup', r'/register', r'/reset-password',
    r'/page/\d+',  # paginated archives
    r'/tag/',  r'/category/',  # taxonomy pages
    r'\.(xml|json|rss|atom)$',  # feeds/data
    r'/wp-admin', r'/wp-json',  # WordPress internals
    r'/cdn-cgi/',  # Cloudflare internals
]
```

**Score URLs by probable importance:**

- Pages linked from the main navigation (`<nav>`) → high priority
- Pages in the header/footer → medium priority
- Pages only found in sitemap → lower priority
- Depth from homepage (fewer clicks = more important)
- URL path depth (`/docs` > `/docs/api/v2/legacy/endpoint`)

**Implement actual BFS crawl:**

- Track visited URLs and depth
- Respect `max_depth=2` properly
- Prioritize shorter URL paths and navigation links

**Smarter cap management:**

- Instead of hard cap at 50, keep the top N by score
- Or: send the LLM a larger list but instruct it to pick the top N

---

## How Data Flows Into the LLM

### Step 2: Metadata Extraction (`services/extractor.py`)

For each discovered URL, fetch the page and extract:

- `title` from `<title>` tag (fallback: `og:title`, then URL)
- `description` from `<meta name="description">` (fallback: `og:description`)
- `h1` from first `<h1>` tag

Returns `list[PageMeta(url, title, description, h1)]`.

**Current issue:** Fetches are sequential (one at a time). There's a TODO to add concurrent fetching with `asyncio.gather` + semaphore. For 50 pages at 1-3s each, this step alone can take 1-2 minutes.

### Step 2b: Homepage Markdown

The homepage URL is fetched separately through `fetch_and_convert()` (from `content_fetcher.py`), which:

1. Fetches the HTML
2. Strips nav, footer, header, script, style, noscript, aside tags
3. Converts remaining HTML to markdown via `markdownify`

This homepage markdown gives the LLM rich context about what the site actually does.

### Step 3: LLM Categorization (`services/llm/*.py` + `prompts/categorize.py`)

This is where the discovered URLs become a structured llms.txt. The LLM receives:

```
┌──────────────────────────────────────────────────────────┐
│ SYSTEM PROMPT (categorize.py)                            │
│                                                          │
│ • llms.txt spec (format rules)                           │
│ • Instructions: pick site name, write description,       │
│   write details, group pages into 2-6 sections,          │
│   use "Optional" for secondary content                   │
│ • Guidelines: <15 word descriptions, ~10 main links,     │
│   every page in exactly one section                      │
├──────────────────────────────────────────────────────────┤
│ USER PROMPT (build_categorize_user_prompt)                │
│                                                          │
│ • Site URL                                               │
│ • client_info (optional user context about the site)     │
│ • user_preferences (optional output preferences)         │
│ • Flat list of all pages:                                │
│     - URL: https://...                                   │
│       Title: Page Title                                  │
│       Description: meta description or (none)            │
│ • Homepage markdown (if < 10,000 chars, inlined)         │
└──────────────────────────────────────────────────────────┘
```

**Two execution modes based on homepage size:**


| Homepage size              | Mode          | Behavior                                                                                                             |
| -------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------- |
| < 10,000 chars             | **Inline**    | Homepage markdown included directly in user prompt                                                                   |
| ≥ 10,000 chars (Anthropic) | **Tool-use**  | LLM gets `search_homepage(query)` tool, searches homepage content by keyword with 3-line context. Max 5 tool rounds. |
| ≥ 10,000 chars (OpenAI)    | **Truncated** | Homepage truncated to 10,000 chars + `[... truncated ...]`                                                           |


**LLM output (JSON):**

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

**What the LLM decides:**

- Which pages go in which section
- What the sections are called
- Page descriptions (rewrites missing/bad ones)
- What goes in "Optional" vs primary sections
- The LLM *can* drop pages entirely (instructions say "every page in exactly one section" but there's no enforcement)

**Problems with how data reaches the LLM:**

1. **Flat, unranked page list.** The LLM sees 50 pages in discovery order with no signal about which are important. Navigation structure, link depth, and page prominence are all lost.
2. **Missing descriptions are common.** Many pages have `(none)` for description, forcing the LLM to guess from titles alone. The LLM could make better decisions if it had actual page content snippets.
3. **No structural hints.** The LLM doesn't know which pages were in the site's navigation, which were buried deep, or which had the most internal links pointing to them.
4. **Homepage markdown is optional/truncated.** For large sites (which are the ones that need the most help), the LLM gets the least homepage context.

### Optimization Opportunities for LLM Input

**Enrich the page list with signals:**

```
- URL: https://example.com/docs
  Title: Documentation
  Description: Complete API reference and guides
  Source: navigation, sitemap     ← where was this found?
  Depth: 1                        ← clicks from homepage
  Internal links: 24              ← how many pages link here?
```

**Send a pre-filtered, ranked list:**
Instead of dumping all 50 URLs, score them first and send the top 30 with scores. Let the LLM focus on curation, not filtering.

**Extract first-paragraph summaries for pages missing descriptions:**
During metadata extraction, grab the first `<p>` tag content as a fallback description. Much better than `(none)`.

**Consider two-pass approach:**

1. First pass: send URLs + titles only, ask LLM to identify the 20 most important pages
2. Second pass: send those 20 with full descriptions + homepage context for detailed categorization

---

## Post-LLM Pipeline

### Step 4: Content Fetching (`services/content_fetcher.py`)

After LLM categorization, every URL in the structured output is fetched and converted to markdown:

```
structured_data.sections[*].pages[*].url
  → fetch_child_pages(urls, concurrency=5)
    → For each URL:
        1. GET page (httpx, 15s timeout)
        2. Parse HTML (BeautifulSoup + lxml)
        3. Find content: <main> → <article> → <body> fallback
        4. Strip: nav, footer, header, script, style, noscript, aside
        5. Convert to markdown (markdownify, skip images)
        6. Extract <title>
    → Returns: ChildPageContent(url, title, markdown_content)
    → Failed pages silently skipped
```

### Step 5: Context Assembly (`services/generator.py`)

Three output formats are built:

`**assemble_base_markdown(structured_data)**` → `llms.txt` with original URLs

```markdown
# Site Name
> One sentence description.
Details paragraph...

## Section Name
- [Page Title](https://original-url.com): Description
```

`**assemble_md_markdown(structured_data, child_pages, site_url)**` → `llms.txt` with .md URLs

```markdown
## Section Name
- [Page Title](https://site.com/page-title.md): Description
```

Slug generation: title → lowercase, strip special chars, spaces to hyphens, cap at 80 chars.

`**assemble_llms_ctx(structured_data, child_pages)**` → `llms-ctx.txt` with inlined content

```markdown
## Section Name
<doc url="https://..." title="Page Title">
Full markdown content of the page...
</doc>
```

Pages without fetched content fall back to link + description format.

### Step 6: Summarize (Currently Disabled)

Intended to take the llms-ctx and run a second LLM pass to refine the structured_data. Not yet implemented.

---

## Endpoints


| Method | Path                              | Purpose                                                                                                                                               |
| ------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/generate`                   | Start generation. Body: `{url, client_info?}`. Returns `{job_id}`.                                                                                    |
| `GET`  | `/api/generate/{id}/stream`       | SSE stream. Events: `progress`, `complete`, `error`.                                                                                                  |
| `POST` | `/api/generate/{id}/download.zip` | Build ZIP from user-edited markdown. Body: `{markdown}`. Returns ZIP with `base/llms.txt`, `md/llms.txt`, `llms-ctx.txt`, and individual `.md` files. |
| `POST` | `/api/validate`                   | Validate markdown against llms.txt spec. Body: `{markdown}`. Returns issues list.                                                                     |


---

## SSE Progress Events

Each pipeline step reports progress through `StepProgressReporter`:

```json
{"type": "progress", "step": "crawl", "status": "started", "message": "Discovering pages..."}
{"type": "progress", "step": "crawl", "detail": "Sitemap: 34 URLs"}
{"type": "progress", "step": "crawl", "status": "completed", "message": "Found 34 pages"}
{"type": "progress", "step": "metadata", "status": "started", ...}
{"type": "progress", "step": "ai_categorize", "detail": "...partial LLM output..."}
{"type": "progress", "step": "fetch_content", ...}
{"type": "progress", "step": "assemble", ...}
{"type": "complete", "markdown": "# Site Name\n> ..."}
```

---

## File Map


| File                              | Role                                                    |
| --------------------------------- | ------------------------------------------------------- |
| `app/main.py`                     | FastAPI app, CORS, logging middleware                   |
| `app/config.py`                   | Pydantic `BaseSettings` — env vars                      |
| `app/models.py`                   | `GenerateRequest`, `PageMeta`, `ChildPageContent`, etc. |
| `app/routers/generate.py`         | Generation endpoints + SSE streaming                    |
| `app/routers/validate.py`         | `/api/validate`                                         |
| `app/services/pipeline.py`        | Orchestrator — runs steps 1–7, manages Queue            |
| `app/services/crawler.py`         | URL discovery (sitemap + link crawl)                    |
| `app/services/extractor.py`       | HTML → PageMeta extraction                              |
| `app/services/content_fetcher.py` | HTML → markdown conversion (child pages)                |
| `app/services/generator.py`       | Markdown assembly (base, md, ctx) + `slugify()`         |
| `app/services/llm/base.py`        | Abstract `LLMProvider`                                  |
| `app/services/llm/factory.py`     | Provider selection from config                          |
| `app/services/llm/anthropic.py`   | Anthropic API (streaming + tool use)                    |
| `app/services/llm/openai.py`      | OpenAI API (streaming, no tool use)                     |
| `app/prompts/categorize.py`       | System/user prompts + `search_homepage` tool            |
| `app/services/validator.py`       | llms.txt spec compliance checker                        |
| `app/testing/mock_llm.py`         | Mock data for `MOCK_LLM=true`                           |


## Configuration


| Var                          | Default                      | Purpose                                 |
| ---------------------------- | ---------------------------- | --------------------------------------- |
| `LLM_PROVIDER`               | `"anthropic"`                | Anthropic vs OpenAI                     |
| `LLM_MODEL`                  | `"claude-sonnet-4-20250514"` | Model for categorization                |
| `MAX_PAGES`                  | `50`                         | URL discovery cap                       |
| `CRAWL_TIMEOUT`              | `30`                         | Seconds for page fetches                |
| `CONTENT_FETCH_CONCURRENCY`  | `5`                          | Concurrent child page fetches           |
| `HOMEPAGE_CONTENT_THRESHOLD` | `10000`                      | Chars before switching to tool-use mode |
| `MOCK_LLM`                   | `true`                       | Skip real LLM calls                     |
| `FRONTEND_URL`               | `http://localhost:5173`      | CORS origin                             |


---

## Summary of Optimization Opportunities

### High Impact

1. **Pre-filter junk URLs** before sending to LLM — exclude login, admin, API, pagination, taxonomy, and feed URLs using pattern matching
2. **Concurrent metadata extraction** — switch from sequential to `asyncio.gather` with semaphore (could cut step 2 time by 5-10x)
3. **Enrich page data with structural signals** — navigation presence, link depth, internal link count — so the LLM can make informed ranking decisions
4. **Extract first-paragraph fallback** for pages with no meta description, giving the LLM actual content to work with

### Medium Impact

1. **Implement real BFS crawl** with depth tracking for sites without sitemaps
2. **URL scoring/ranking** before LLM — prioritize navigation links, shallow pages, and frequently-linked pages
3. **Two-pass LLM approach** — quick triage pass to pick top pages, then detailed categorization pass
4. **Normalize URLs** more aggressively — trailing slashes, www vs non-www, case normalization

### Lower Impact

1. **Skip fetching "Optional" section pages** in step 4 — they're secondary content
2. **Enable the summarize step** (step 6) — use llms-ctx to refine the initial categorization
3. **Cache fetched pages** — avoid re-fetching homepage in step 2b when it was already fetched in step 2
4. **Sitemap index support** — follow `<sitemap>` entries in sitemap indexes to discover sub-sitemaps

