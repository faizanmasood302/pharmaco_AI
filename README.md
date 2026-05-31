# Pharmacogenomic Harness

**AI agent harness for n-of-1 prescribing decisions** — built for [YC's AI Personalized Medicine](https://www.ycombinator.com/rfs) request.

Modern prescribing is still population-average. That drives two crises: **$1.45T** in substance abuse (genetically vulnerable patients get dangerous opioid spikes from prodrugs like codeine) and **$290B** in non-adherence (ineffective metabolism → side effects → patients stop therapy).

We intercept the prescription **before dispensing**: ingest n-of-1 genetic data (CYP2D6 phenotype), run a multi-agent pipeline, and **change the treatment decision** when biology and drug don't match.

## Demo (60 seconds)

1. Start backend: `cd agent-server && uv run uvicorn main:app --reload`
2. Start frontend: `cd web && npm run dev`
3. Open [http://localhost:3000](http://localhost:3000)
4. **(Optional)** Import FHIR sample → new patient in dropdown
5. Select **Maria Chen (Ultra-Rapid CYP2D6)** + **Codeine** → **Evaluate**
6. See: **CRITICAL** block, safe alternative (Duloxetine), agent pipeline, pulsing 3D metabolic warning
7. **Control:** Sarah Patel + Pregabalin → approved → **Start adherence monitoring**

**Deploy:** See [DEPLOY.md](DEPLOY.md).

## Architecture

| Layer | Stack | Role |
|-------|--------|------|
| Web | Next.js 16, R3F, GSAP | Clinician UI, visual informatics alert |
| Agent server | FastAPI, Python 3.12 | Multi-agent PGx orchestration |
| Rules engine | Deterministic CPIC-aligned CYP2D6 rules | Reliable demo + production core |
| Optional LLM | Groq | Clinical narrative enrichment |
| Data | In-memory seed patients (+ optional Supabase) | Synthetic FHIR-ready profiles |

**Agent pipeline:** Research → Analyst → Critic → Orchestrator (+ Adherence agent post-approval)

**API highlights:** `POST /api/ingest-fhir`, `GET /api/evaluations/{id}`, `POST /api/adherence/plans`

## Quick start

### Prerequisites

- Python 3.12+ with [uv](https://github.com/astral-sh/uv)
- Node.js 20+

### Backend

```bash
cd agent-server
uv sync
# optional: copy .env.example to .env and set GROQ_API_KEY
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd web
npm install
# optional: .env.local with AGENT_SERVER_URL=http://127.0.0.1:8000
npm run dev
```

## Environment variables

| Variable | Where | Required |
|----------|--------|----------|
| `GROQ_API_KEY` | agent-server | No (deterministic rules work without it) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | agent-server | No (uses seed patients) |
| `AGENT_SERVER_URL` | web | No (defaults to `http://127.0.0.1:8000`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | web | No (auth skipped if unset) |

## Go-to-market wedge

Per `ARCHITECTURE.md`: bypass 12–18 month hospital EHR cycles by targeting **boutique pain clinics** and **DTC telehealth** with synthetic/FHIR-linked PGx ingestion.

## YC application

See [YC_APPLICATION.md](./YC_APPLICATION.md) for pitch framing aligned with Ankit Gupta's RFS.

## Disclaimer

Synthetic demo data only. Not a medical device. Not for clinical use.
