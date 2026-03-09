# Frontend Engineer Memory

## Environment
- Node v24.3.0
- Run dev server: `cd frontend && npm run dev` (port 5173, proxies to backend :8000)
- Build: `cd frontend && npm run build` (`tsc -b && vite build`)
- Config: `frontend/.env` with `VITE_API_URL=http://localhost:8000`

## Tech Stack
- React 19, TypeScript 5.7+, Vite 6, Tailwind CSS 4 (with `@tailwindcss/vite`)
- `marked` for markdown rendering, `@tailwindcss/typography` for prose styles
- SSE (EventSource) for real-time job progress
- No client-side router — single page app

## Tailwind CSS v4
- Uses `@tailwindcss/vite` plugin (NOT PostCSS)
- Config via `@theme` directive in `frontend/src/index.css`, NOT `tailwind.config.ts`
- Custom tokens use `profound-*` prefix

## Design System (see `frontend/src/index.css`)
- Dark theme: black background
- Colors: `profound-yellow` (#FFEA35), `profound-card` (#141414), `profound-border` (#1F1F1F), `profound-muted` (#A1A1AA)
- Fonts: Inter (sans), JetBrains Mono (mono)

## File Structure (`frontend/src/`)
- `main.tsx` — React entry point
- `App.tsx` — main app component, job orchestration
- `types/index.ts` — Job, GenerateRequest/Response, RepromptRequest/Response, ValidateRequest/Response
- `lib/api.ts` — generic `request<T>` wrapper, exports `startGeneration`, `reprompt`, `validate`
- `lib/markdown.ts` — markdown rendering utilities
- `hooks/useSSE.ts` — EventSource connection management
- `hooks/useJob.ts` — orchestrates full job lifecycle (generate → SSE → result)
- `components/Layout.tsx` — page shell, header/footer
- `components/URLInput.tsx` — URL input form
- `components/PipelineProgress.tsx` — real-time pipeline step progress
- `components/Editor.tsx` — markdown editor (textarea)
- `components/EditorPreview.tsx` — side-by-side editor + preview
- `components/Preview.tsx` — rendered markdown preview
- `components/ExportBar.tsx` — download/copy/export actions

## Component Patterns
- Default exports for components, named exports for hooks/utils
- Functional components with hooks only
- Props interfaces defined inline or in types/index.ts

## API Integration
- `POST /api/generate` → returns job_id → `GET /api/generate/{jobId}/stream` for SSE progress
- `POST /api/reprompt` → send instructions + existing markdown → get modified markdown
- `POST /api/validate` → validate llms.txt markdown against spec

## Dependencies (package.json)
- Runtime: react, react-dom, marked, @tailwindcss/typography
- Dev: tailwindcss, @tailwindcss/vite, @vitejs/plugin-react, typescript, vite, @types/react, @types/react-dom
