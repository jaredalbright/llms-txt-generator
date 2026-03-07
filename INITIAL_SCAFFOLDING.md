# llms.txt Generator — Claude Code Scaffolding Spec

> This spec is a blueprint for Claude Code to scaffold the entire monorepo. It is intentionally
> detailed about structure, wiring, and patterns, but marks non-critical integration points
> (Supabase, full crawl logic, prompt tuning) as `TODO` so the developer can fill them in
> incrementally. The goal is a running app with the right architecture from the first commit.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Monorepo Structure](#2-monorepo-structure)
3. [Design System & Brand](#3-design-system--brand)
4. [Frontend Spec (React + Vite + Tailwind)](#4-frontend-spec)
5. [Backend Spec (FastAPI + Python)](#5-backend-spec)
6. [Database (Supabase)](#6-database-supabase)
7. [Async Pipeline & SSE](#7-async-pipeline--sse)
8. [LLM Provider Abstraction](#8-llm-provider-abstraction)
9. [API Contract](#9-api-contract)
10. [Deployment](#10-deployment)
11. [TODO Checklist](#11-todo-checklist)

---

## 1. Project Overview

### What We're Building

A web application that takes a URL as input, crawls the target website, extracts metadata, uses
an LLM to categorize and summarize the pages, and produces a spec-compliant `llms.txt` file
the user can edit, reprompt, and download.

### The llms.txt Spec (from llmstxt.org)

The output Markdown file must follow this exact structure:

```markdown
# Site Name

> A one-sentence summary of what this site is.

Optional context paragraphs (no headings allowed here).

## Section Name

- [Page Title](https://example.com/page): Short description
- [Another Page](https://example.com/other): Another description

## Optional

- [Less Critical Page](https://example.com/extra): Supplementary info
```

Rules:
- H1 (required): The name of the site.
- Blockquote (recommended): A short summary.
- Body text (optional): Additional context paragraphs, lists — no headings.
- H2 sections (optional): Each contains a Markdown list of links.
- Each link: `[name](url)` optionally followed by `: description`.
- The H2 `## Optional` has special semantics — its links can be skipped for shorter contexts.

### Core User Flows

1. **Generate**: User enters a URL → async crawl + AI processing → llms.txt displayed in editor.
2. **Edit**: User manually edits the generated Markdown in a text editor with live preview.
3. **Reprompt**: User provides additional instructions (e.g., "move the blog posts to Optional") → LLM re-processes with the new instruction applied to the current output.
4. **Regenerate**: User clicks regenerate → full pipeline runs again from scratch.
5. **Download**: User downloads the final llms.txt as a `.txt` or `.md` file.

---

## 2. Monorepo Structure

Use a simple folder-based monorepo. No Turborepo, Nx, or workspaces overhead needed for
two packages. A root-level `package.json` (or just a README) ties it together.

```
llms-txt-generator/
├── README.md
├── .gitignore
├── frontend/                     # React + Vite + Tailwind
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── .env.example              # VITE_API_URL=http://localhost:8000
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css              # Tailwind directives + custom fonts
│       ├── components/
│       │   ├── Layout.tsx         # Shell: header, main content area
│       │   ├── URLInput.tsx       # URL input form with validation
│       │   ├── ProgressView.tsx   # Crawl progress display (pages found, status)
│       │   ├── Editor.tsx         # Markdown textarea (left pane)
│       │   ├── Preview.tsx        # Rendered Markdown preview (right pane)
│       │   ├── EditorPreview.tsx  # Split-pane container for Editor + Preview
│       │   ├── RepromptBar.tsx    # Text input for follow-up AI instructions
│       │   ├── ExportBar.tsx      # Download + copy-to-clipboard buttons
│       │   └── StatusBadge.tsx    # Shows job state (crawling, generating, done, error)
│       ├── hooks/
│       │   ├── useSSE.ts          # Custom hook for SSE connection management
│       │   └── useJob.ts          # Job state management (submit, poll, receive)
│       ├── lib/
│       │   ├── api.ts             # API client (fetch wrappers for all endpoints)
│       │   └── markdown.ts        # Markdown rendering utility (using marked or similar)
│       └── types/
│           └── index.ts           # Shared TypeScript types (Job, Page, GenerationResult)
│
├── backend/                       # FastAPI + Python
│   ├── pyproject.toml             # or requirements.txt — dependencies
│   ├── .env.example               # API keys, Supabase URL, etc.
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app, CORS, SSE endpoint, routes
│   │   ├── config.py              # Pydantic Settings (env var management)
│   │   ├── models.py              # Pydantic models (request/response schemas)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── generate.py        # POST /generate, GET /generate/{job_id}/stream
│   │   │   └── validate.py        # POST /validate
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── crawler.py         # URL discovery (sitemap + fallback link crawl)
│   │   │   ├── extractor.py       # HTML → metadata extraction
│   │   │   ├── llm/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py        # Abstract LLM provider interface
│   │   │   │   ├── anthropic.py   # Claude Sonnet implementation
│   │   │   │   ├── openai.py      # GPT-4o-mini implementation
│   │   │   │   └── factory.py     # Provider factory (reads config, returns provider)
│   │   │   ├── generator.py       # Assembles llms.txt Markdown from structured data
│   │   │   ├── validator.py       # Spec compliance checker
│   │   │   └── pipeline.py        # Orchestrates: crawl → extract → LLM → assemble
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── client.py          # Supabase client initialization
│   │   │   └── jobs.py            # CRUD operations for jobs table
│   │   └── prompts/
│   │       ├── categorize.py      # System + user prompt for page categorization
│   │       ├── summarize.py       # Prompt for site name + summary generation
│   │       └── reprompt.py        # Prompt template for user reprompt instructions
│   └── tests/
│       ├── __init__.py
│       ├── test_generator.py      # Unit tests for Markdown assembly
│       └── test_validator.py      # Unit tests for spec validation
```

---

## 3. Design System & Brand

### Profound's Visual Identity (Reference: tryprofound.com)

The app should feel like it belongs in the same product family as Profound — dark, minimal,
with sharp yellow accents and clean typography.

### Colors (Tailwind Config)

```
Brand Yellow (Primary Accent):   #FFEA35    → "profound-yellow"
Black (Background):              #000000    → default black
Dark Surface:                    #0A0A0A    → "profound-surface"
Dark Card/Panel:                 #141414    → "profound-card"
Border/Divider:                  #1F1F1F    → "profound-border"
Light Gray (Secondary Text):     #A1A1AA    → "profound-muted"
Athens Gray (Subtle):            #E5E7EB    → "profound-light"
White (Primary Text):            #FFFFFF    → default white
Error Red:                       #EF4444    → Tailwind red-500
Success Green:                   #22C55E    → Tailwind green-500
```

### Typography

Use **Inter** as the primary font (Google Fonts, variable weight). It's a clean geometric
sans-serif that matches Profound's aesthetic — highly legible, modern, works at all sizes.
Use **JetBrains Mono** for the Markdown editor / code display areas.

```css
/* index.css */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-black text-white font-sans antialiased;
  }
}
```

### Tailwind Config Extension

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        profound: {
          yellow: '#FFEA35',
          surface: '#0A0A0A',
          card: '#141414',
          border: '#1F1F1F',
          muted: '#A1A1AA',
          light: '#E5E7EB',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

### UI Patterns

- **Buttons (Primary):** `bg-profound-yellow text-black font-semibold rounded-lg px-6 py-2.5
  hover:bg-yellow-300 transition-colors`. No borders. Bold text on yellow.
- **Buttons (Secondary/Ghost):** `border border-profound-border text-white rounded-lg px-6 py-2.5
  hover:bg-profound-card transition-colors`.
- **Input Fields:** `bg-profound-card border border-profound-border rounded-lg px-4 py-3
  text-white placeholder:text-profound-muted focus:border-profound-yellow focus:ring-1
  focus:ring-profound-yellow outline-none transition-colors`.
- **Cards/Panels:** `bg-profound-card border border-profound-border rounded-xl p-6`.
- **Page Background:** Full black (`bg-black`). Content area max-width ~1200px, centered.
- **Section Headings:** `text-2xl font-semibold text-white`. Minimal — no decorative elements.
- **Status Pills:** Rounded full, small text.
  - Crawling: `bg-yellow-500/10 text-yellow-400`
  - Processing: `bg-blue-500/10 text-blue-400`
  - Complete: `bg-green-500/10 text-green-400`
  - Error: `bg-red-500/10 text-red-400`

### Layout

Single-page app. No routing needed. The page flows vertically:

```
┌──────────────────────────────────────────┐
│  Header: Logo / App Name                 │
├──────────────────────────────────────────┤
│  URL Input Bar                           │
│  [ https://example.com        ] [Generate]│
├──────────────────────────────────────────┤
│  Status Badge (crawling / generating...) │
├──────────────────────────────────────────┤
│  ┌─────────────────┬────────────────────┐│
│  │  Markdown Editor │  Rendered Preview  ││
│  │  (textarea/      │  (HTML output of   ││
│  │   CodeMirror)    │   the Markdown)    ││
│  │                  │                    ││
│  │                  │                    ││
│  └─────────────────┴────────────────────┘│
├──────────────────────────────────────────┤
│  Reprompt Bar                            │
│  [ "Move blog posts to Optional" ] [Send]│
├──────────────────────────────────────────┤
│  Export Bar: [Download .txt] [Copy] [Regenerate] │
└──────────────────────────────────────────┘
```

The editor/preview section and everything below it should be hidden until a generation has
completed. Show the ProgressView component during crawling/processing.

---

## 4. Frontend Spec

### Setup

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install -D tailwindcss @tailwindcss/vite
npm install marked         # Markdown → HTML rendering
```

### Key Components

#### `URLInput.tsx`
- Single text input + submit button.
- Basic URL validation (must start with `http://` or `https://`).
- On submit: calls `POST /api/generate` with `{ url }`, receives `{ job_id }`.
- Disables input while a job is in progress.

#### `ProgressView.tsx`
- Displayed while job status is `crawling` or `processing`.
- Shows: current status label, number of pages discovered (from SSE updates).
- Animated spinner or pulsing dot for visual polish.
- Receives progress data from the `useSSE` hook.

#### `EditorPreview.tsx`
- Displayed when job status is `completed`.
- Two-pane split: left is `Editor`, right is `Preview`.
- Responsive: stack vertically on mobile, side-by-side on desktop.
- Use CSS Grid or Flexbox with `w-1/2` each.

#### `Editor.tsx`
- A `<textarea>` styled with the mono font, dark background.
- Contains the generated llms.txt Markdown.
- User can freely edit the text.
- On every change, updates the parent state so Preview re-renders.
- **Stretch goal:** Replace textarea with CodeMirror 6 for syntax highlighting. For the
  scaffold, a styled textarea is sufficient.

#### `Preview.tsx`
- Takes the current Markdown string, renders to HTML using `marked`.
- Styled to look like a rendered document (proper heading sizes, blockquote styling, link
  colors).
- Read-only display.

#### `RepromptBar.tsx`
- Text input + submit button.
- On submit: calls `POST /api/reprompt` with `{ job_id, instruction, current_markdown }`.
- Returns an updated Markdown string that replaces the editor content.
- The LLM receives the current llms.txt + the user's instruction and returns a modified version.

#### `ExportBar.tsx`
- **Download .txt:** Creates a Blob from the editor content, triggers download as `llms.txt`.
- **Download .md:** Same, but as `llms.md`.
- **Copy to clipboard:** `navigator.clipboard.writeText(...)` with a brief "Copied!" toast.
- **Regenerate:** Re-triggers the full pipeline from scratch for the same URL.

### Hooks

#### `useSSE.ts`
```typescript
// Connects to GET /api/generate/{job_id}/stream
// Listens for SSE events:
//   event: "progress"  → data: { status, pages_found, message }
//   event: "complete"  → data: { markdown, job_id }
//   event: "error"     → data: { message }
// Returns: { status, progress, result, error, isConnected }
// Automatically reconnects once on drop. Cleans up on unmount.

import { useState, useEffect, useRef } from 'react';

interface SSEProgress {
  status: 'crawling' | 'processing' | 'completed' | 'error';
  pages_found?: number;
  message?: string;
}

interface SSEResult {
  markdown: string;
  job_id: string;
}

export function useSSE(jobId: string | null) {
  const [status, setStatus] = useState<SSEProgress['status'] | null>(null);
  const [progress, setProgress] = useState<SSEProgress | null>(null);
  const [result, setResult] = useState<SSEResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const es = new EventSource(`${apiUrl}/api/generate/${jobId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('progress', (e) => {
      const data: SSEProgress = JSON.parse(e.data);
      setStatus(data.status);
      setProgress(data);
    });

    es.addEventListener('complete', (e) => {
      const data: SSEResult = JSON.parse(e.data);
      setStatus('completed');
      setResult(data);
      es.close();
    });

    es.addEventListener('error', (e) => {
      // SSE spec fires 'error' for both connection issues and server errors
      // Check if we got a data payload (server error) vs connection drop
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setError(data.message);
        setStatus('error');
      } catch {
        // Connection error — EventSource will auto-reconnect by default
        setError('Connection lost. Reconnecting...');
      }
    });

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [jobId]);

  return { status, progress, result, error };
}
```

#### `useJob.ts`
```typescript
// Orchestrates the full flow:
// 1. submitJob(url) → POST /api/generate → job_id
// 2. Passes job_id to useSSE
// 3. Exposes: submitJob, regenerate, reprompt, markdown (editable), status, progress, error

export function useJob() {
  // State: jobId, markdown, status, etc.
  // submitJob(url): POST to backend, set jobId → triggers useSSE
  // regenerate(): re-submit same URL
  // reprompt(instruction): POST /api/reprompt → update markdown
  // setMarkdown: for manual edits
  // Return all state + actions
}
```

### Types (`types/index.ts`)

```typescript
export type JobStatus = 'pending' | 'crawling' | 'processing' | 'completed' | 'error';

export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  created_at: string;
  markdown?: string;
  pages_found?: number;
  error_message?: string;
}

export interface GenerateRequest {
  url: string;
}

export interface GenerateResponse {
  job_id: string;
}

export interface RepromptRequest {
  job_id: string;
  instruction: string;
  current_markdown: string;
}

export interface RepromptResponse {
  markdown: string;
}

export interface ValidateRequest {
  markdown: string;
}

export interface ValidationIssue {
  line: number;
  severity: 'error' | 'warning';
  message: string;
}

export interface ValidateResponse {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface PageMeta {
  url: string;
  title: string;
  description: string;
  h1: string;
}
```

---

## 5. Backend Spec

### Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx beautifulsoup4 lxml anthropic openai \
            sse-starlette pydantic-settings supabase python-dotenv
```

Use `pyproject.toml` or `requirements.txt` — either is fine. Pin versions.

### `app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import generate, validate

app = FastAPI(title="llms.txt Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Lock down to frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, prefix="/api")
app.include_router(validate.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

### `app/config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_provider: str = "anthropic"            # "anthropic" | "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"  # or "gpt-4o-mini"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Crawl
    max_pages: int = 50
    crawl_timeout: int = 30                    # seconds per page

    # App
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
```

### `app/models.py`

```python
from pydantic import BaseModel, HttpUrl
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class GenerateRequest(BaseModel):
    url: HttpUrl


class GenerateResponse(BaseModel):
    job_id: str


class RepromptRequest(BaseModel):
    job_id: str
    instruction: str
    current_markdown: str


class RepromptResponse(BaseModel):
    markdown: str


class ValidateRequest(BaseModel):
    markdown: str


class ValidationIssue(BaseModel):
    line: int
    severity: str  # "error" | "warning"
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    issues: list[ValidationIssue]


class PageMeta(BaseModel):
    url: str
    title: str
    description: str
    h1: Optional[str] = None
```

### `app/routers/generate.py`

```python
import asyncio
import uuid
from fastapi import APIRouter, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from app.models import GenerateRequest, GenerateResponse
from app.services.pipeline import run_pipeline

router = APIRouter()

# In-memory job store — replace with Supabase in production
# Key: job_id, Value: { status, pages_found, markdown, error, events: asyncio.Queue }
jobs: dict[str, dict] = {}


@router.post("/generate", response_model=GenerateResponse)
async def create_job(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    event_queue = asyncio.Queue()

    jobs[job_id] = {
        "status": "pending",
        "url": str(req.url),
        "pages_found": 0,
        "markdown": None,
        "error": None,
        "event_queue": event_queue,
    }

    # Fire and forget — runs in background
    background_tasks.add_task(run_pipeline, job_id, str(req.url), jobs)

    return GenerateResponse(job_id=job_id)


@router.get("/generate/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE endpoint. Client connects here after POST /generate returns job_id."""
    if job_id not in jobs:
        return {"error": "Job not found"}

    job = jobs[job_id]

    async def event_generator():
        queue: asyncio.Queue = job["event_queue"]

        while True:
            event = await queue.get()

            if event["type"] == "progress":
                yield {
                    "event": "progress",
                    "data": {
                        "status": event["status"],
                        "pages_found": event.get("pages_found", 0),
                        "message": event.get("message", ""),
                    },
                }

            elif event["type"] == "complete":
                yield {
                    "event": "complete",
                    "data": {
                        "markdown": event["markdown"],
                        "job_id": job_id,
                    },
                }
                return  # Close the stream

            elif event["type"] == "error":
                yield {
                    "event": "error",
                    "data": {
                        "message": event["message"],
                    },
                }
                return

    return EventSourceResponse(event_generator())
```

### `app/services/pipeline.py`

```python
import asyncio
from app.services.crawler import crawl_site
from app.services.extractor import extract_metadata
from app.services.llm.factory import get_llm_provider
from app.services.generator import assemble_markdown


async def run_pipeline(job_id: str, url: str, jobs: dict):
    """
    Full async pipeline:
    1. Crawl the site (discover URLs)
    2. Extract metadata from each page
    3. Send to LLM for categorization + summarization
    4. Assemble the final Markdown
    5. Push result via SSE event queue
    """
    job = jobs[job_id]
    queue: asyncio.Queue = job["event_queue"]

    try:
        # --- Step 1: Crawl ---
        await queue.put({
            "type": "progress",
            "status": "crawling",
            "message": "Discovering pages...",
            "pages_found": 0,
        })

        urls = await crawl_site(url)

        await queue.put({
            "type": "progress",
            "status": "crawling",
            "message": f"Found {len(urls)} pages. Extracting metadata...",
            "pages_found": len(urls),
        })

        # --- Step 2: Extract ---
        pages = await extract_metadata(urls)

        await queue.put({
            "type": "progress",
            "status": "processing",
            "message": "Analyzing site structure with AI...",
            "pages_found": len(pages),
        })

        # --- Step 3: LLM ---
        llm = get_llm_provider()
        structured_data = await llm.categorize_pages(url, pages)

        # --- Step 4: Assemble ---
        markdown = assemble_markdown(structured_data)

        # --- Step 5: Done ---
        job["status"] = "completed"
        job["markdown"] = markdown

        await queue.put({
            "type": "complete",
            "markdown": markdown,
        })

        # TODO: Persist to Supabase
        # await db.jobs.update(job_id, status="completed", markdown=markdown)

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        await queue.put({
            "type": "error",
            "message": f"Generation failed: {str(e)}",
        })
```

### `app/services/crawler.py`

```python
import httpx
from xml.etree import ElementTree
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.config import settings


async def crawl_site(url: str) -> list[str]:
    """
    Discover URLs for the given site.
    Strategy:
      1. Try /sitemap.xml first (fast, comprehensive).
      2. Fall back to crawling links from homepage.
    Returns deduplicated list of same-domain URLs, capped at settings.max_pages.
    """
    base_domain = urlparse(url).netloc
    discovered: set[str] = set()

    # --- Try sitemap ---
    sitemap_urls = await _try_sitemap(url)
    if sitemap_urls:
        discovered.update(sitemap_urls)

    # --- Fallback: crawl from homepage ---
    if len(discovered) < 5:
        crawled = await _crawl_links(url, base_domain, max_depth=2)
        discovered.update(crawled)

    # Always include the homepage
    discovered.add(url.rstrip("/"))

    # Filter to same domain, deduplicate, cap
    filtered = [u for u in discovered if urlparse(u).netloc == base_domain]
    return filtered[:settings.max_pages]


async def _try_sitemap(url: str) -> list[str]:
    """Fetch and parse /sitemap.xml. Returns list of URLs or empty list."""
    sitemap_url = urljoin(url, "/sitemap.xml")

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(sitemap_url)
            if resp.status_code != 200:
                return []

        root = ElementTree.fromstring(resp.text)
        # Handle both regular sitemaps and sitemap indexes
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//ns:loc", ns) if loc.text]
        return urls

    except Exception:
        return []


async def _crawl_links(start_url: str, base_domain: str, max_depth: int = 2) -> set[str]:
    """
    BFS crawl from start_url, following internal links.
    TODO: Implement full BFS with depth tracking and visited set.
    For scaffold, just extract links from the homepage.
    """
    found: set[str] = set()

    try:
        async with httpx.AsyncClient(
            timeout=settings.crawl_timeout,
            follow_redirects=True,
            headers={"User-Agent": "llms-txt-generator/1.0"}
        ) as client:
            resp = await client.get(start_url)
            if resp.status_code != 200:
                return found

            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(start_url, href)
                parsed = urlparse(full_url)

                # Same domain, no fragments, no query params
                if parsed.netloc == base_domain:
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
                    found.add(clean)

    except Exception:
        pass

    return found
```

### `app/services/extractor.py`

```python
import httpx
from bs4 import BeautifulSoup
from app.models import PageMeta


async def extract_metadata(urls: list[str]) -> list[PageMeta]:
    """
    Fetch each URL and extract title, meta description, h1.
    Uses concurrent requests for speed.
    """
    pages: list[PageMeta] = []

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "llms-txt-generator/1.0"},
    ) as client:
        # TODO: Use asyncio.gather with concurrency limit (semaphore) for speed
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                title = ""
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()

                description = ""
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    description = meta_desc["content"].strip()

                # Fallback to og:description
                if not description:
                    og_desc = soup.find("meta", attrs={"property": "og:description"})
                    if og_desc and og_desc.get("content"):
                        description = og_desc["content"].strip()

                h1 = ""
                h1_tag = soup.find("h1")
                if h1_tag:
                    h1 = h1_tag.get_text(strip=True)

                pages.append(PageMeta(
                    url=url,
                    title=title or h1 or url,
                    description=description,
                    h1=h1,
                ))

            except Exception:
                # Skip pages that fail — don't break the whole pipeline
                continue

    return pages
```

### `app/services/generator.py`

```python
from typing import Any


def assemble_markdown(structured_data: dict[str, Any]) -> str:
    """
    Takes the structured JSON from the LLM and builds a spec-compliant llms.txt string.

    Expected structured_data format:
    {
        "site_name": "Example Corp",
        "summary": "A platform for doing X.",
        "context": "Optional additional context paragraph.",   # optional
        "sections": [
            {
                "name": "Docs",
                "pages": [
                    {"title": "Getting Started", "url": "https://...", "description": "How to..."},
                ]
            },
            {
                "name": "Optional",
                "pages": [...]
            }
        ]
    }
    """
    lines: list[str] = []

    # H1 — required
    lines.append(f"# {structured_data['site_name']}")
    lines.append("")

    # Blockquote summary
    if structured_data.get("summary"):
        lines.append(f"> {structured_data['summary']}")
        lines.append("")

    # Optional context paragraphs
    if structured_data.get("context"):
        lines.append(structured_data["context"])
        lines.append("")

    # H2 sections with link lists
    for section in structured_data.get("sections", []):
        lines.append(f"## {section['name']}")
        lines.append("")
        for page in section.get("pages", []):
            title = page.get("title", page["url"])
            url = page["url"]
            desc = page.get("description", "")
            if desc:
                lines.append(f"- [{title}]({url}): {desc}")
            else:
                lines.append(f"- [{title}]({url})")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
```

### `app/services/validator.py`

```python
import re
from app.models import ValidationIssue


def validate_llms_txt(markdown: str) -> list[ValidationIssue]:
    """
    Check a Markdown string for llms.txt spec compliance.

    Checks:
    1. Must start with H1 (# Site Name)
    2. Should have a blockquote summary (> ...)
    3. No H2 before any body text/blockquote
    4. H2 sections should contain link lists
    5. Links should be in [name](url) format
    6. No H3+ headings allowed
    """
    issues: list[ValidationIssue] = []
    lines = markdown.strip().split("\n")

    if not lines:
        issues.append(ValidationIssue(line=1, severity="error", message="File is empty"))
        return issues

    # Check H1
    if not lines[0].startswith("# ") or lines[0].startswith("## "):
        issues.append(ValidationIssue(
            line=1,
            severity="error",
            message="File must start with an H1 heading (# Site Name)"
        ))

    # Check for blockquote
    has_blockquote = any(line.strip().startswith("> ") for line in lines)
    if not has_blockquote:
        issues.append(ValidationIssue(
            line=2,
            severity="warning",
            message="Missing blockquote summary (> description)"
        ))

    # Check for forbidden headings (H3+)
    for i, line in enumerate(lines):
        if re.match(r'^#{3,}\s', line):
            issues.append(ValidationIssue(
                line=i + 1,
                severity="error",
                message="H3+ headings are not allowed in llms.txt"
            ))

    # Check link format in list items
    link_pattern = re.compile(r'^-\s+\[.+\]\(https?://.+\)')
    in_section = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_section = True
            continue
        if in_section and line.strip().startswith("- "):
            if not link_pattern.match(line.strip()):
                issues.append(ValidationIssue(
                    line=i + 1,
                    severity="warning",
                    message="List item should be in format: - [Title](url): description"
                ))

    return issues
```

---

## 6. Database (Supabase)

### Purpose

Persist job results so users can revisit them, and so we have generation history for debugging
and future features.

### Schema

```sql
-- Run this in Supabase SQL Editor

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',        -- pending | crawling | processing | completed | error
    markdown TEXT,
    pages_found INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Optional: store discovered pages for debugging
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    description TEXT,
    h1 TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pages_job_id ON pages(job_id);
```

### Backend Client (`app/db/client.py`)

```python
from supabase import create_client, Client
from app.config import settings

# TODO: Initialize once Supabase project is created and env vars are set
# supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

def get_supabase() -> Client:
    """
    TODO: Uncomment and use once Supabase is configured.
    For now, the app runs with in-memory job storage (see routers/generate.py).
    """
    # return supabase
    raise NotImplementedError("Supabase not configured yet — using in-memory storage")
```

### Job CRUD (`app/db/jobs.py`)

```python
"""
TODO: Implement these once Supabase is connected.
For now, the in-memory dict in routers/generate.py handles job state.
When ready, swap the in-memory dict for these functions.
"""


async def create_job(url: str) -> str:
    """Insert a new job row, return the UUID."""
    # result = supabase.table("jobs").insert({"url": url, "status": "pending"}).execute()
    # return result.data[0]["id"]
    raise NotImplementedError


async def update_job(job_id: str, **kwargs):
    """Update job fields (status, markdown, pages_found, error_message)."""
    # supabase.table("jobs").update(kwargs).eq("id", job_id).execute()
    raise NotImplementedError


async def get_job(job_id: str) -> dict:
    """Fetch a single job by ID."""
    # result = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    # return result.data
    raise NotImplementedError
```

---

## 7. Async Pipeline & SSE

### How It Works

```
Client                           Server
  │                                 │
  ├── POST /api/generate {url} ──► │ Creates job, returns job_id
  │                                 │ Kicks off run_pipeline() as BackgroundTask
  │                                 │
  ├── GET /api/generate/{id}/stream │
  │   (EventSource connection)      │
  │                                 │
  │  ◄── SSE: progress (crawling)   │ Pipeline puts events on asyncio.Queue
  │  ◄── SSE: progress (processing) │
  │  ◄── SSE: complete (markdown)   │ Stream closes
  │                                 │
  ├── POST /api/reprompt ─────────► │ Synchronous LLM call, returns new markdown
  │  ◄── { markdown }               │
  │                                 │
  ├── (user edits locally)          │
  │                                 │
  ├── Download (client-side only)   │
  │                                 │
```

### Key Design Decisions

1. **`asyncio.Queue` per job**: Each job gets its own queue. The SSE endpoint reads from
   the queue. The background pipeline writes to it. This decouples the two cleanly.

2. **Client reconnection**: If the SSE connection drops, the client can reconnect to the same
   `/stream` endpoint. If the job already completed, the endpoint should immediately send
   the `complete` event with the cached markdown. The job dict (or Supabase row) holds the
   final state.

3. **No WebSockets**: SSE is simpler, one-directional (server → client), works through
   proxies and load balancers, and is sufficient for this use case. The client only sends
   data via regular POST requests.

4. **Reprompt is synchronous**: Unlike the initial generation (which involves crawling),
   reprompting is just an LLM call on existing data. It can be a regular request/response
   cycle — no need for SSE.

---

## 8. LLM Provider Abstraction

### Base Interface (`app/services/llm/base.py`)

```python
from abc import ABC, abstractmethod
from app.models import PageMeta


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers must implement these methods.
    """

    @abstractmethod
    async def categorize_pages(
        self, site_url: str, pages: list[PageMeta]
    ) -> dict:
        """
        Given a site URL and list of page metadata, return structured data:
        {
            "site_name": str,
            "summary": str,
            "context": str | None,
            "sections": [
                {
                    "name": str,
                    "pages": [{"title": str, "url": str, "description": str}]
                }
            ]
        }
        """
        pass

    @abstractmethod
    async def reprompt(
        self, current_markdown: str, instruction: str
    ) -> str:
        """
        Given the current llms.txt markdown and a user instruction,
        return the modified markdown.
        """
        pass
```

### Anthropic Implementation (`app/services/llm/anthropic.py`)

```python
import json
import anthropic
from app.services.llm.base import LLMProvider
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import CATEGORIZE_SYSTEM_PROMPT, build_categorize_user_prompt
from app.prompts.reprompt import REPROMPT_SYSTEM_PROMPT, build_reprompt_user_prompt


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model

    async def categorize_pages(self, site_url: str, pages: list[PageMeta]) -> dict:
        user_prompt = build_categorize_user_prompt(site_url, pages)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=CATEGORIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract JSON from response
        text = response.content[0].text
        # Handle potential markdown code fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text.strip())

    async def reprompt(self, current_markdown: str, instruction: str) -> str:
        user_prompt = build_reprompt_user_prompt(current_markdown, instruction)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=REPROMPT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text.strip()
```

### OpenAI Implementation (`app/services/llm/openai.py`)

```python
import json
from openai import AsyncOpenAI
from app.services.llm.base import LLMProvider
from app.models import PageMeta
from app.config import settings
from app.prompts.categorize import CATEGORIZE_SYSTEM_PROMPT, build_categorize_user_prompt
from app.prompts.reprompt import REPROMPT_SYSTEM_PROMPT, build_reprompt_user_prompt


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model  # e.g., "gpt-4o-mini"

    async def categorize_pages(self, site_url: str, pages: list[PageMeta]) -> dict:
        user_prompt = build_categorize_user_prompt(site_url, pages)

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": CATEGORIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = response.choices[0].message.content
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        return json.loads(text.strip())

    async def reprompt(self, current_markdown: str, instruction: str) -> str:
        user_prompt = build_reprompt_user_prompt(current_markdown, instruction)

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": REPROMPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        return response.choices[0].message.content.strip()
```

### Factory (`app/services/llm/factory.py`)

```python
from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.openai import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    """
    Returns the configured LLM provider based on settings.llm_provider.
    Swap providers by changing the LLM_PROVIDER env var.
    """
    match settings.llm_provider:
        case "anthropic":
            return AnthropicProvider()
        case "openai":
            return OpenAIProvider()
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
```

---

## 9. API Contract

### `POST /api/generate`

Starts a new generation job.

**Request:**
```json
{ "url": "https://example.com" }
```

**Response (202):**
```json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000" }
```

### `GET /api/generate/{job_id}/stream`

SSE stream for job progress.

**Events:**
```
event: progress
data: {"status": "crawling", "pages_found": 12, "message": "Discovering pages..."}

event: progress
data: {"status": "processing", "pages_found": 34, "message": "Analyzing with AI..."}

event: complete
data: {"markdown": "# Site Name\n\n> Summary\n\n## Docs\n...", "job_id": "550e..."}

event: error
data: {"message": "Failed to crawl: connection timeout"}
```

### `POST /api/reprompt`

Synchronous. Sends current markdown + instruction to LLM, returns modified markdown.

**Request:**
```json
{
  "job_id": "550e8400-...",
  "instruction": "Move the blog posts into an Optional section",
  "current_markdown": "# Site Name\n\n> Summary\n\n## Docs\n..."
}
```

**Response (200):**
```json
{ "markdown": "# Site Name\n\n> Summary\n\n## Docs\n...\n## Optional\n..." }
```

### `POST /api/validate`

Validates a llms.txt Markdown string against the spec.

**Request:**
```json
{ "markdown": "# My Site\n\n> A summary.\n\n## Docs\n- [Page](https://...)..." }
```

**Response (200):**
```json
{
  "valid": true,
  "issues": []
}
```

Or with issues:
```json
{
  "valid": false,
  "issues": [
    { "line": 1, "severity": "error", "message": "File must start with an H1 heading" },
    { "line": 5, "severity": "warning", "message": "List item should be in [Title](url) format" }
  ]
}
```

### `GET /health`

```json
{ "status": "ok" }
```

---

## 10. Deployment

### Frontend → Vercel

1. Connect the GitHub repo to Vercel.
2. Set the **Root Directory** to `frontend`.
3. Framework preset: **Vite**.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Environment variable: `VITE_API_URL` = your Railway backend URL (e.g., `https://llms-txt-api.up.railway.app`).

### Backend → Railway

1. Connect the same GitHub repo to Railway.
2. Set the **Root Directory** to `backend`.
3. Railway auto-detects Python. If not, set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Environment variables:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY` (optional, if using OpenAI)
   - `LLM_PROVIDER=anthropic`
   - `LLM_MODEL=claude-sonnet-4-20250514`
   - `SUPABASE_URL` (TODO: once created)
   - `SUPABASE_KEY` (TODO: once created)
   - `FRONTEND_URL` = your Vercel URL

### Supabase

1. Create a project at supabase.com.
2. Run the SQL from [Section 6](#6-database-supabase) in the SQL Editor.
3. Copy the project URL and anon key into Railway env vars.

### Custom Domain (Optional)

- Vercel: Add a custom domain in project settings.
- Railway: Add a custom domain or use the `.up.railway.app` subdomain.

---

## 11. TODO Checklist

These items are intentionally left as stubs or marked TODO in the scaffold. They should be
filled in incrementally after the initial scaffolding is running.

### Must Do (Core Functionality)

- [ ] **Crawl depth**: Implement BFS crawl with depth tracking in `crawler.py` (currently only does homepage links)
- [ ] **Concurrent extraction**: Add `asyncio.Semaphore` to `extractor.py` for parallel page fetching
- [ ] **Prompt engineering**: Write and iterate on prompts in `prompts/categorize.py` and `prompts/summarize.py`
- [ ] **Reprompt prompt**: Write the prompt template in `prompts/reprompt.py`
- [ ] **Error boundaries**: Add proper error handling in all frontend components
- [ ] **SSE reconnection**: Handle reconnection in `useSSE.ts` when job already completed (return cached result)
- [ ] **robots.txt**: Check robots.txt before crawling pages

### Should Do (Polish)

- [ ] **Supabase integration**: Uncomment and wire up `db/client.py` and `db/jobs.py`, replace in-memory dict
- [ ] **Reprompt endpoint**: Implement `POST /api/reprompt` in a router (currently spec'd but not routed)
- [ ] **Validate endpoint**: Wire up `POST /api/validate` router
- [ ] **Loading states**: Add skeleton/shimmer states during crawl
- [ ] **Mobile responsive**: Stack editor/preview vertically on small screens
- [ ] **Copy feedback**: Toast notification on copy-to-clipboard

### Nice to Have (If Time Permits)

- [ ] **CodeMirror editor**: Replace textarea with CodeMirror 6 for Markdown syntax highlighting
- [ ] **Validate tab**: Separate UI mode where users paste existing llms.txt for validation
- [ ] **Job history**: List previous generations (requires Supabase)
- [ ] **Rate limiting**: Add rate limiting on the generate endpoint
- [ ] **Crawl progress granularity**: Send SSE events per-page as they're discovered
- [ ] **Sitemap index support**: Handle nested sitemap indexes (sitemap of sitemaps)

---

## Prompts (Starter Templates)

### `app/prompts/categorize.py`

```python
CATEGORIZE_SYSTEM_PROMPT = """You are an expert at analyzing website structure. You will receive
a list of pages from a website (URL, title, description). Your job is to:

1. Choose a clean, human-readable site name (not the raw domain).
2. Write a one-sentence summary of what the site does.
3. Group the pages into logical sections using H2 names like: Docs, API Reference, Guides,
   Blog, About, Pricing, Legal, Support, etc. Use whatever section names best fit the content.
4. Decide which pages are secondary/supplementary and put them in an "Optional" section.
5. For pages missing descriptions, write a concise one-sentence description.

Return ONLY valid JSON with this exact structure (no markdown fences, no explanation):
{
  "site_name": "Human Readable Site Name",
  "summary": "One sentence describing what this site is.",
  "context": null,
  "sections": [
    {
      "name": "Section Name",
      "pages": [
        {"title": "Page Title", "url": "https://...", "description": "What this page covers."}
      ]
    }
  ]
}

Guidelines:
- Keep section count between 2-6. Don't over-categorize.
- Every page must appear in exactly one section.
- The "Optional" section (if used) should contain genuinely secondary content: legal pages,
  old blog posts, changelog entries, etc.
- Descriptions should be concise (under 15 words) and informative.
- Site name should be the product/company name, not the domain."""


def build_categorize_user_prompt(site_url: str, pages: list) -> str:
    page_list = "\n".join(
        f"- URL: {p.url}\n  Title: {p.title}\n  Description: {p.description or '(none)'}"
        for p in pages
    )
    return f"""Analyze this website and categorize its pages for an llms.txt file.

Website: {site_url}

Pages found:
{page_list}

Return the JSON structure as specified."""
```

### `app/prompts/reprompt.py`

```python
REPROMPT_SYSTEM_PROMPT = """You are editing an llms.txt file based on user instructions.
You will receive the current llms.txt Markdown and an instruction from the user.
Apply the instruction and return the complete, modified llms.txt Markdown.

Rules:
- Maintain valid llms.txt format: H1, blockquote, optional body text, H2 sections with link lists.
- Only change what the instruction asks for. Don't reorganize everything.
- Return ONLY the Markdown content. No explanation, no code fences."""


def build_reprompt_user_prompt(current_markdown: str, instruction: str) -> str:
    return f"""Current llms.txt:

{current_markdown}

---

User instruction: {instruction}

Return the updated llms.txt Markdown."""
```
