# llms.txt Generator - Frontend Memory

## Project Structure
- **Root**: `/Users/jaredalbright/Projects/llms-txt-generator/`
- **Frontend**: `frontend/` - React 19 + TypeScript + Vite 6 + Tailwind CSS 4
- **Backend**: Proxied at `http://localhost:8000` via Vite dev server

## Tech Stack
- React 19, TypeScript 5.7+, Vite 6, Tailwind CSS 4 (with `@tailwindcss/vite`)
- `marked` for markdown rendering
- SSE (EventSource) for real-time job progress
- No router - single page app

## Design System (see `frontend/src/index.css`)
- Dark theme: black bg, custom tokens prefixed `profound-`
- Colors: `profound-yellow` (#FFEA35), `profound-card` (#141414), `profound-border` (#1F1F1F), `profound-muted` (#A1A1AA)
- Fonts: Inter (sans), JetBrains Mono (mono)

## Architecture
- **Types**: `src/types/index.ts` - Job, GenerateRequest/Response, RepromptRequest/Response, ValidateRequest/Response
- **API client**: `src/lib/api.ts` - generic `request<T>` wrapper, exports `startGeneration`, `reprompt`, `validate`
- **Hooks**: `useSSE` (EventSource connection), `useJob` (orchestrates job lifecycle)
- **Components**: Layout, URLInput, StatusBadge, ProgressView, Editor, Preview, EditorPreview, RepromptBar, ExportBar
- **Pattern**: Default exports for components, named exports for hooks/utils

## API Endpoints
- `POST /api/generate` - start generation job
- `GET /api/generate/{jobId}/stream` - SSE progress stream
- `POST /api/reprompt` - reprompt with instructions
- `POST /api/validate` - validate markdown
