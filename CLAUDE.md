# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository shape

GenomicLens — a pharmacogenomic clinical decision support system. A clinician submits a patient ID plus a proposed drug; the system returns a risk assessment with CPIC-cited evidence, alternatives, and an audit trail behind a human approval gate.

Two deployable units:

- `agent-server/` — Python 3.12 / FastAPI backend. All clinical logic lives here.
- `web/` — Next.js 16 / React 19 frontend. Its `src/app/api/*` routes are thin proxies to the backend, not a second business-logic layer.

Research and education only. Synthetic data only. Not a medical device, and no code path may present it as one.

## Active feature: 001-pgx-safety-harness

**This is a rebuild, not a remediation.** The existing implementation is treated as untrustworthy
and is being replaced against the spec below. Existing behaviour is evidence of what went wrong and
material for regression tests — never precedent for what to keep. Where existing code conflicts with
the spec, the spec wins.

Read in this order before touching anything non-trivial:

| Document | Role |
|---|---|
| `HARNESS.md` | v1.1. The binding architecture spec. Governs everything below it; amendment log at the foot of the file |
| `.specify/memory/constitution.md` | v1.0.1. Ten principles, each naming its enforcement mechanism and owning test file |
| `specs/001-pgx-safety-harness/spec.md` | 64 functional requirements, 18 success criteria, 10 prioritised stories |
| `specs/001-pgx-safety-harness/plan.md` | Phases 0–9, sequenced by the constitution's Delivery Order |
| `specs/001-pgx-safety-harness/data-model.md` | Domain types, database schema, gate state machine |
| `specs/001-pgx-safety-harness/contracts/openapi.yaml` | The v1 API surface — every endpoint takes identifiers |
| `docs/adr/` | Decisions the constitution forbids picking silently |

### Target stack (plan.md Technical Context)

The new tree is `agent-server/src/{domain,engines,evidence,ai,platform,api}`, built alongside the
legacy tree, under an `import-linter` contract. The legacy tree survives until Phase 8 because
Phase 1 must measure it to produce the "before" figure.

- PostgreSQL 16 with `pgvector` and `tsvector`, RRF fusion in SQL. No separate vector service
- `psycopg` v3 async pool. Not per-query connections
- PharmCAT as a separate pinned service over HTTP. Not a subprocess
- OpenAI Agents SDK, `Agent.as_tool()` only — `handoff()` prohibited, no tool wraps an engine call,
  SDK tracing disabled (ADR-0005). Provider stays Anthropic `claude-opus-5` via LiteLLM (ADR-0004).
  The OpenAI-compatible layer does not guarantee schema conformance and ignores `strict`, so schema
  parse-failure rate is a **measured** metric, not an assumption
- Severity is a four-level scale, retained deliberately (ADR-0006). The CPIC-strength→severity
  mapping lives in reviewable policy data with a named reviewer, never in the enum
- PharmCAT cannot call CNV, so CYP2D6 ultrarapid is unreachable **from a VCF** — but reachable
  through the outside-call path, which is the fixture and FHIR path. A second caller (PyPGx) covers
  the VCF path only (ADR-0007)
- `testcontainers` for a real Postgres in tests. The database is never mocked — the CHECK constraint
  and the generated `provisional` column are enforcement mechanisms a mock cannot exercise
- `mypy --strict` on `src/domain/` and `src/engines/`; `pydantic` v2 with `frozen=True`,
  `extra="forbid"`

`HARNESS.md` is at **v1.1** (amended 2026-08-23, amendment log at the foot of the file) and the
constitution at **v1.0.1**. The amendments replaced the IX.1 orchestration row, removed the
unsettable sampling parameters from IX.1/IX.6, and renamed `ai/graph` → `ai/orchestration`
throughout — there is no graph module. Plan items P0-1 and P0-2 are discharged.

## `HARNESS.md` is the binding architecture spec

Read it before any non-trivial change. It supersedes `AGENTS.md` and `ARCHITECTURE-V2.md`, and it is an audit of commit `31e5f88` — which is at or near HEAD, so **its findings describe the code as it is now, not a past state.**

Its central thesis governs every design decision here:

> In safety-critical medicine, an LLM is a rendering and inquiry layer over a verified deterministic core, never the source of a clinical judgment. Every guarantee the system makes must be enforced by a mechanism outside the model.

**Part II is binding.** Ten invariants, each owning a test file under `tests/invariants/`. Do not implement anything that violates one — raise the conflict instead.

| # | Invariant |
|---|---|
| I1 | No LLM output becomes a risk level, a drug choice, or a gate decision |
| I2 | Unknown is a first-class value that halts (no default phenotype branch) |
| I3 | Every recommended drug has been assessed for *this* patient |
| I4 | The system is fully functional with the LLM disabled (`LLM_ENABLED=false`) |
| I5 | Every clinical claim carries provenance to a guideline table |
| I6 | Over-flagging is a tracked failure, not a safe default |
| I7 | Server state is never read from the client |
| I8 | Citations verified against the pinned corpus before display |
| I9 | Input contradictions halt; never reconciled by a model |
| I10 | The review gate is not counted as a safety control |

Two consequences that are easy to get wrong:

- **`NO_GUIDANCE` and `HALTED` are outcomes, not severities, and are not orderable against them.** `Severity` is an `IntEnum`; `Outcome` is not. Any `max()` that can turn a halt into a `"low"` is the exact mechanism of the audited critical failure.
- **The human gate is a workflow and accountability mechanism, not a safety control (I10).** Evidence in Part I.C: an incorrect flag raised prescribing errors 56.9%, and override rates below ~5% signal automation bias rather than quality. Never cite human review as mitigation for engine error in code comments, docs, or risk write-ups.

Part X is the delivery order, ranked by clinical risk removed per unit of work. Steps 1–4 (golden set + concordance CI gate · typed phenotype with halting unknowns · alternatives re-assessed for the same patient · gate re-read server-side with a content hash) remove most of the risk. Part XI held 11 open decisions that must be recorded in `docs/adr/` when resolved — **do not silently pick one.** Six are now closed (ADR-0001 through ADR-0003, ADR-0005 through ADR-0007); five remain, one of them external.

## Commands

Backend (`cd agent-server`):

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

uv run pytest tests/ -q                          # full suite
uv run pytest tests/test_rules.py -q             # one file
uv run pytest tests/test_rules.py::test_name -q  # one test
uv run pytest tests/ -q --ignore=tests/test_regression.py   # skip the slow 225-combination sweep

uv run ruff check .        # lint (line-length 88, target py312)
uv run ruff format .
uv run mypy .              # strict; excludes tests/, venv/
```

`pytest.ini` sets `asyncio_mode = auto`, so `async def test_*` needs no decorator. `tests/conftest.py` sets `SECRET_KEY`/`ENCRYPTION_KEY` and autouses a fixture that unsets `GROQ_API_KEY` and blanks `DATABASE_URL` — but see the import-time caveat below.

Frontend (`cd web`):

```bash
npm install
npm run dev      # next dev
npm run build    # next build — this is what CI gates on
npm run lint     # eslint
npm run test     # vitest run
npx vitest run src/__tests__/EvaluationPanel.test.tsx   # single test file
```

Whole stack: `docker compose up` (needs `agent-server/.env`).

CI (`.github/workflows/ci.yml`) runs exactly two jobs: backend `pytest tests/` and frontend `npm run build`. Lint, mypy, and the frontend tests are **not** gated — run them locally. The spec's target pipeline (Part IX.5) adds `invariants`, `llm-disabled`, `concordance`, `alert-burden`, `determinism`, and `contracts` jobs; none exist yet.

Env vars: see `.env.example`. Backend needs `GROQ_API_KEY`, `SECRET_KEY`, `ENCRYPTION_KEY`, optionally `DATABASE_URL`. Frontend needs `AGENT_SERVER_URL`, `BETTER_AUTH_SECRET`.

## Architecture as built

### The deterministic core is the authority

`pgx/rules.py::assess_prescription(patient_id, medication, patient=None) -> RiskAssessment` is the single source of clinical truth. Every agent fallback path routes through it (commit `31e5f88` exists specifically to fix a case where one did not). If you touch clinical logic, you are touching this function or the seed data behind it — not an agent prompt.

Drug knowledge is version-controlled JSON validated by Pydantic at import: `pgx/seed/drugs.json` (enzyme, prodrug status, alternatives), `pgx/seed/guidelines.json` (per-phenotype CPIC/DPWG text), `pgx/seed/schema.py`. **Load fails closed** — a malformed entry prevents startup. Add drugs here, never as literals in code.

### Request flow

```
POST /api/evaluate-prescription
  -> agents/orchestrator.py (re-export) -> agents/orchestrator_agent.py::evaluate_prescription
      -> _run_specialists()  - 5 agents via asyncio.gather:
            rx_risk · evidence · adherence · misuse · cost_navigator
      -> _adjudicate()       - _llm_adjudicate() if Groq available, else _deterministic_adjudicate()
      -> EvaluationResponse (verdict · findings · agent_steps · audit_trail · logic_tree · human_gate)
  -> POST /api/clinical-note  - requires human_gate.status == "approved"
```

Agents reach tools through `agents/mcp_client.py`, which spawns the five stdio servers in `mcps/*/mcp_server.py` (pgx-tools, pgx-rules-engine, fhir-service, patient-db, clinical-reporter) and **falls back to direct Python calls on any failure**. The audit found this fallback silent enough that the entire MCP layer could be broken with no observable difference. Do not add logic that only exists on one side of that boundary.

### Backend module map

| Path | Role |
|---|---|
| `main.py` | FastAPI routes, rate limiting (slowapi), correlation-ID middleware, exception handlers |
| `models.py` | All Pydantic wire contracts (`EvaluationResponse`, `HumanGate`, `SpecialistOpinion`, …) |
| `pgx/rules.py` | `assess_prescription`, `normalize_medication`, per-gene phenotype getters, `RiskLevel`/`CpicLevel` |
| `pgx/patients.py` | Patient records and phenotype extraction |
| `agents/` | Specialists, orchestrator, reporter, tool loop (`base.py`), MCP client |
| `db/database.py` | Postgres access; `db/vector_store.py` wraps ChromaDB |
| `fhir/parser.py` | FHIR R4 bundle to patient profile |
| `knowledge/` | CPIC/FDA guideline markdown, embedded into the vector store |
| `auth.py` `crypto.py` `audit.py` | JWT verification, Fernet PII encryption, append-only audit log |

### Frontend

`web/src/lib/api.ts` is the single backend client; `schema.ts` holds the Zod mirrors of the backend contracts; `types.ts` the TS types. Components of note: `EvaluationPanel.tsx` (the main flow), `ReviewFlowPanel.tsx` (the human gate), `TherapySimulationPanel.tsx`, `MetabolicScene.tsx` / `PathwayVisualizer.tsx` (three.js visualisation). The Zod schemas are hand-maintained, not generated — when you change a backend Pydantic model, update `schema.ts` in the same change or the frontend fails at runtime instead of at build.

## Known divergences from the spec

These are live defects the spec names. Do not treat existing code as precedent for them, and do not "fix" them as drive-by edits inside unrelated work — they are Part X line items.

- **I4 is not wired.** `agents/reporter.py` builds its Groq client at *import* time (module level, in a `try/except`), so `conftest.py`'s `monkeypatch.delenv("GROQ_API_KEY")` runs too late. It also reads `ENABLE_LLM_NOTES`, not the `LLM_ENABLED` that the spec's invariant and ablation study (Part VII.5) both name. The documented kill switch is currently connected to nothing.
- **The engine makes network calls.** `pgx/rules.py::rxnorm_lookup` hits `https://rxnav.nlm.nih.gov/REST` live from `normalize_medication` when a local match fails. This breaks determinism (Part VII.3 calls a failure here P0) and the no-network-in-tools rule (IV.3). Any concordance number measured before this is pinned is not reproducible.
- **I7 is violated at `main.py::create_note`.** The endpoint takes a full `EvaluationResponse` body and reads `result.human_gate.status` from it. Per IV.6/IV.10 it must accept `{evaluation_id}` only, load server-side, fold the transition history, and re-verify an `assessment_sha256` content hash.
- **The adjudicator still exists.** `_llm_adjudicate` in `orchestrator_agent.py` lets a model synthesise specialist opinions into a decision. Part I.F12 and I1 mark this the core anti-pattern; Part X step 7 deletes it.
- **`agents/base.py::parse_opinion`** regexes a JSON object out of prose and returns `{}` on failure — "clinical meaning derived from prose," in the Part VIII failure catalogue.
- **`agents/base.py` tool loop (~L122–144)** appends one synthetic assistant message *per* tool call inside the iteration, instead of one assistant message carrying all calls followed by all results together. This silently suppresses parallel tool calling.
- **Measurement is manual and stale.** `CONCORDANCE_MEMO.md` is a hand-run 28-row table marked HISTORICAL, with a measured 46% concordance and 29% false-positive rate. `README.md` and `PITCH_DECK.md` quote higher estimates. There is no automated golden set, no `eval/`, and no `tests/invariants/`. Part X step 1 exists to fix this first, and step 14 to correct the documents afterwards.
- **Target layout does not exist.** The spec's `src/domain` · `src/engines` · `src/ai` split with an `import-linter` contract (IV.8) is the destination, not the current tree. Today's `agent-server/` has no enforced layer boundary, which is why I1 is aspirational rather than mechanical.

## Working rules

- **Clinical values come from `assess_prescription` or the seed tables. Never from an LLM, and never from string-matching guideline prose.** Two audited criticals came from `"avoid" in evidence.lower()`-style checks and substring phenotype matching.
- **Unknown never becomes normal.** A gene the assay did not cover must be represented explicitly, not omitted. Absence is what let the audited system default to "normal metabolizer" and proceed.
- **An alternative is only offerable if it was assessed against this same patient's genotype** (I3). The audited system offered duloxetine as a codeine substitute because it had no indication and never re-scored candidates.
- **Never add a fallback verdict.** Tool failure, DB write failure, and provider outage produce typed errors or template degradation — never a success-shaped low-risk response.
- **False positives are a co-primary metric, not a safe default** (I6). Over-flagging is the dominant deployed failure mode of this product category; a change that raises alert burden must justify itself.
- Keep `tests/test_regression.py` passing — it sweeps every patient × drug combination with the LLM forced off. Note it asserts *liveness* (no exception, non-None risk level), not correctness; the spec calls this out as an anti-pattern that the golden set replaces.
- The "not for clinical use" research-only disclaimer is a regulatory boundary (Part III), not boilerplate. It belongs on the README, API root, every UI surface, and every generated document footer.
