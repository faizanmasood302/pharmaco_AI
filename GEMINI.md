# Pharmacogenomic (PGx) Agent Harness

## Project Overview
The Pharmacogenomic (PGx) Agent Harness is a dual-pipeline prototype for auditable pharmacogenomic decision support and N-of-1 therapy research simulation. It uses synthetic demo data, deterministic guardrails, and human review gates to explore workflows. 

**Note: This is a research simulation prototype, not for clinical use.** The project processes synthetic data only and must never process real PII or PHI.

### Architecture
The project is built around Agentic Orchestration with Deterministic Guardrails:
- **Backend (`/agent-server`):** FastAPI application powered by Python, utilizing LangGraph-style agent orchestration, Groq/Llama models, and a bioinformatics adapter. It acts as the core intelligence layer.
- **Frontend (`/web`):** Next.js dashboard application utilizing React, TypeScript, Tailwind CSS, BetterAuth, and Three.js (for metabolic canvases/3D elements). It provides the Prescription Console and N-of-1 Research Workspace.
- **Data & Memory:** Uses Supabase (PostgreSQL) for relational state and an Obsidian-compatible Markdown vault for long-term clinical policies and patient timelines.

## Building and Running

The project can be run via Docker Compose or locally via respective package managers. **Note:** Environment variables must be set up in `agent-server/.env` and `web/.env.local` prior to running.

### Full Stack (Docker)
```bash
docker-compose up --build
```

### Backend (`/agent-server`)
Managed with `uv` (Python >=3.12).
- **Install:** `uv sync`
- **Run:** `uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- **Test:** `uv run pytest tests/ -q`
- **Lint & Types:** Uses `ruff` (line-length 88) and `mypy` (strict mode).

### Frontend (`/web`)
Managed with `npm` (Node.js).
- **Install:** `npm install`
- **Run (Dev):** `npm run dev`
- **Build:** `npm run build`
- **Test:** `npm run test` (Vitest)
- **Lint:** `npm run lint` (ESLint)

## Development Conventions

- **Security & Data:** STRICTLY synthetic demo data. Do not add real patient data. Refer to `SECURITY.md`.
- **Backend Standards:** Follow `ruff` conventions outlined in `pyproject.toml`. Ensure strict typing with `mypy`.
- **Frontend Standards:** Next.js App Router conventions with Tailwind CSS for styling. Code should be strictly typed with TypeScript.
- **Database:** Supabase configuration and schemas are located in the `/supabase` directory. To initialize, run `supabase/seed.sql` in your Supabase instance.
- **Architecture Documentation:** See `ARCHITECTURE.md`, `AGENT_ARCHITECTURE.md`, and `FUTURE_ARCHITECTURE.md` in the root directory for in-depth system design principles.
