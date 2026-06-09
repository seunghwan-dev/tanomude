# tanomude frontend

Operator approval console for the tanomude agent: the 3-tab approval card (分析 / 計画 / 根拠)
rendered from real `POST /tasks/plan` data, plus the 承認 / 修正 / 却下 action shell wired to the
decision endpoints.

Stack: Vite + React 18 + TypeScript + Tailwind CSS + Framer Motion.

In development the Vite dev server (`:5173`) proxies `/api` and `/ws` to the agent API. In production the backend serves this built frontend itself, same-origin on `:8000`, with no proxy.

## Running (full stack)

The card calls the agent API, which needs the platform RAG store, the embedding service, and a
local LLM. Plan generation (`POST /tasks/plan`) does **not** require the mock-as400.

1. **Backend services** (from the repo root):

   ```
   docker compose up -d platform-db embedding
   ```

   and have Ollama running locally with the configured model pulled (`OLLAMA_URL`, default
   `http://localhost:11434`).

2. **Ingest the operation manual** into the platform DB once, so the 根拠 (grounding) tab is populated.
   The full `docker compose up` stack seeds this manual automatically on first boot; these manual steps are only for this dev path. From `backend/` (venv active, env vars set):

   ```python
   from backend.db import SessionLocal
   from backend.ingest import ingest_manual, load_manual
   with SessionLocal() as db:
       ingest_manual(db, workflow="shutchou", title="出張申請 操作マニュアル",
                     source="shukko_manual.md", markdown=load_manual("shukko_manual.md"))
   ```

3. **Agent API** (from `backend/`):

   ```
   PLATFORM_DATABASE_URL=postgresql+psycopg://tanomude:tanomude@localhost:5433/platform \
   EMBEDDING_URL=http://localhost:8001 \
   OLLAMA_URL=http://localhost:11434 \
   DATABASE_URL=postgresql+psycopg://tanomude:tanomude@localhost:5432/mock_as400 \
   uvicorn backend.agent.app:app --port 8000
   ```

4. **Frontend** (from `frontend/`):

   ```
   npm install
   npm run dev
   ```

   Open http://localhost:5173. The Vite dev server proxies `/api/*` to the agent API on
   `http://localhost:8000`, so no CORS configuration is needed on the backend.

## Scripts

- `npm run dev` — dev server with API proxy
- `npm run build` — typecheck (`tsc`) + production build (`vite build`)
- `npm run preview` — serve the production build locally
