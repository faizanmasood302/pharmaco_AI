# Quickstart — 001 PGx Safety Harness

How to run the system, measure it, and verify that each invariant is actually enforced rather than
merely described. Commands marked **(Phase N)** do not exist yet; they land with that phase and are
listed here so the plan's deliverables are checkable.

Research and education only. Synthetic data only. Not a medical device.

## Prerequisites

- Python 3.12+ and `uv`
- Node 20+ and `pnpm`
- Docker (PostgreSQL 16 + pgvector, MinIO, and the PharmCAT image)

## Backend

```bash
cd agent-server
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000     # legacy tree, until Phase 8
uv run uvicorn src.api.main:app --reload --port 8000            # (Phase 0) new tree
```

## Frontend

```bash
cd web
pnpm install
pnpm dev
pnpm build        # this is what CI gates on
```

## Whole stack

```bash
docker compose up          # app · postgres+pgvector · minio · pharmcat  (Phase 5)
```

Requires `agent-server/.env`. The Compose file must actually build — the audited one referenced a
Dockerfile that did not exist.

## Tests

```bash
cd agent-server

uv run pytest tests/ -q                                  # full suite
uv run pytest tests/invariants/ -q                       # the ten owning test files
uv run pytest tests/test_rules.py::test_name -q          # one test

LLM_ENABLED=false uv run pytest tests/ -q                # the ablation run (Principle IV)

uv run ruff check . && uv run ruff format --check .
uv run mypy src/domain src/engines                       # strict; the invariants are type claims
uv run lint-imports                                      # (Phase 0) the import contract
```

`pytest.ini` sets `asyncio_mode = auto`, so `async def test_*` needs no decorator.

The database is **not** mocked. Integration tests spin up a real PostgreSQL 16 + pgvector container
via `testcontainers`, because two of the enforcement mechanisms live in the schema rather than in
Python: the `phenotype_calls` CHECK constraint and the generated `provisional` column.

## Measurement (Phase 1)

```bash
cd agent-server

uv run python -m eval.concordance --golden eval/golden/ --out eval/scorecards/
LLM_ENABLED=false uv run python -m eval.concordance --golden eval/golden/ --out eval/scorecards/

uv run python -m eval.report eval/scorecards/latest.json     # per gene and per drug class
uv run python -m eval.compare eval/scorecards/baseline.json eval/scorecards/latest.json
```

Scorecards are committed as dated JSON so the delta appears in every diff. Aggregate-only reporting
is prohibited — a 46% aggregate hides which module is broken.

Reported alongside the clinical metrics: narrative refusal rate, omission rate, citation resolution
failure rate, and **schema parse-failure rate** — the OpenAI-compatible layer does not guarantee
schema conformance, so the gap is measured rather than assumed away (ADR-0005).

Reading the numbers:

- **Halt rate rising sharply when Phase 2 lands is not a regression.** It is previously hidden gaps
  becoming visible, and it must be reported that way (SC-015).
- **False positive rate is co-primary, not secondary.** Over-flagging is the dominant deployed
  failure mode of this product category, and a change that raises it must justify itself in the same
  pull request.
- **Two-stage agreement is reported separately** — genotype→phenotype and phenotype+drug→
  recommendation. A combined figure alone is not acceptable (FR-036a).

## Verifying the invariants by hand

Each row is something you can check yourself, not something you have to take on trust.

| Principle | What to run | What proves it |
|---|---|---|
| I — engine authority | `uv run lint-imports` | An added `from src.ai …` inside `src/engines/` fails the build |
| II — unknown halts | `pytest tests/invariants/test_unknown_halts.py` | A profile missing a relevant gene returns `HALTED`, no severity anywhere in the response |
| III — alternatives | `pytest tests/invariants/test_alternatives_assessed.py` | Every returned alternative carries its own `assessment_id`; rejects are present with reasons |
| IV — LLM disabled | `LLM_ENABLED=false uv run pytest tests/ -q` | The full suite passes; verdicts identical to the enabled run |
| V — provenance | `pytest tests/invariants/test_provenance.py` | A policy row with no reviewer field prevents startup |
| VI — alert burden | `uv run python -m eval.report …` | Interruptive-alert rate is reported and gated |
| VII — server state | `curl -X POST /v1/reports -d '{"evaluation_id":"…","status":"approved"}'` | Rejected: `additionalProperties: false`, and status is never read from a body |
| VIII — grounding gate | `pytest tests/invariants/test_grounding_gate.py` | A narrative naming an unassessed drug is refused and the refusal is logged |
| IX — contradictions | `pytest tests/invariants/test_input_contradiction.py` | Two sources disagreeing on one gene halts, naming both |
| X — gate posture | `pytest tests/invariants/test_review_gate_posture.py` | No project document claims human review as mitigation for engine error |

## Environment variables

| Variable | Purpose |
|---|---|
| `LLM_ENABLED` | The ablation switch. Resolved **at call time**, never at import. Not a differently-named substitute |
| `DATABASE_URL` | PostgreSQL 16 with pgvector |
| `PHARMCAT_URL` | The pinned PharmCAT service (Phase 5) |
| `CYP2D6_CALLER_URL` | The CYP2D6 structural-variant caller, VCF path only (Phase 5, ADR-0007) |
| `ANTHROPIC_API_KEY` | Provider credential, used only inside `src/ai/` |
| `SECRET_KEY`, `ENCRYPTION_KEY` | JWT signing and Fernet PII encryption. The app refuses to boot without the latter |
| `S3_ENDPOINT`, `S3_BUCKET` | Tool stdout and generated reports |

`tests/conftest.py` sets `SECRET_KEY` and `ENCRYPTION_KEY` and unsets provider credentials. Note the
known defect this exposes today: the legacy `agents/reporter.py` builds its provider client at
*import* time, so unsetting the key in a fixture runs too late and the documented kill switch is
connected to nothing. Phase 0 fixes that, before anything is measured.

## Where things live

| Path | Contents |
|---|---|
| `agent-server/src/domain/` | Pure types. Zero internal imports |
| `agent-server/src/engines/pgx/` | The deterministic core. Cannot import `src/ai/` |
| `agent-server/src/ai/` | Everything that touches a model, including the grounding gate |
| `agent-server/policy/severity/` | One reviewed YAML per gene |
| `agent-server/tools/registry.yaml` | Pinned tool versions, image digests, licences |
| `agent-server/eval/` | Golden set, concordance harness, committed scorecards |
| `agent-server/tests/invariants/` | Ten files, one per principle |
| `specs/001-pgx-safety-harness/` | This feature's spec, plan, data model and contracts |
| `docs/adr/` | Decisions the constitution forbids picking silently |

---

*Research and education only. Synthetic data only. Not a medical device.*
