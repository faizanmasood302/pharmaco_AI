# Implementation Plan: Constitution-Conformant Pharmacogenomic Safety Harness

**Branch**: `001-pgx-safety-harness` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)
**Constitution**: v1.0.1 (`.specify/memory/constitution.md`) | **Source of record**: `HARNESS.md` v1.1
**Status**: Ready for `/sp.tasks` — P0-1/P0-2 discharged 2026-08-23; `HARNESS.md` now v1.1, constitution v1.0.1

## Summary

Rebuild Engine A as a layered system in which the deterministic core holds all clinical authority
and the model layer is confined to narrative and inquiry, with the boundary enforced by
`import-linter` rather than by review. Work is sequenced by the constitution's Delivery Order:
measurement first, then the defects that produced the audited criticals (unknown-as-normal,
unassessed alternatives, client-supplied approval state), then the reference-implementation swap,
then presentation and posture.

The existing `agent-server/` tree is not reshaped in place. A new `agent-server/src/` tree is built
alongside it under the import contract; the legacy tree survives only long enough to produce the
baseline measurement in Phase 1, and is deleted in Phase 8.

## Technical Context

**Language/Version**: Python 3.12+ (backend); TypeScript 5 / Node 20 (frontend)
**Package management**: `uv` with committed `uv.lock` (backend); `pnpm` (frontend)
**Primary Dependencies**:
`pydantic` v2 (`frozen=True`, `extra="forbid"`) · `fastapi` · `uvicorn`/`gunicorn` · `sse-starlette` ·
`structlog` · `opentelemetry-sdk` · `psycopg[pool]` v3 · `sqlalchemy` 2.0 Core · `alembic` ·
`pgvector` · `fastembed` · `fhir.resources` · `cryptography` · `pyjwt` · `openai-agents[litellm]` ·
`import-linter` · `mypy` · `ruff`
**Storage**: PostgreSQL 16 — relational, `pgvector` dense, `tsvector` lexical, reciprocal-rank fusion
in SQL. No separate vector service. S3-compatible object store (MinIO in dev) for tool stdout and
generated reports.
**External services**: PharmCAT as a separate pinned image behind a thin HTTP wrapper. Not a
subprocess, not Docker-in-Docker.
**Testing**: `pytest` + `pytest-asyncio` + `pytest-cov`; `hypothesis` for phenotype-vocabulary
property tests; `testcontainers` for a real PostgreSQL 16 + pgvector instance. The database is never
mocked — silent write failures passing CI is a catalogued failure (Part VIII).
**Target Platform**: Linux containers. Docker Compose in dev, the same images in production.
**Project Type**: Web — Python backend (`agent-server/src/`) plus Next.js frontend (`web/`).
**Performance Goals**: None numeric. Correctness and reproducibility gates govern. No latency target
is claimed, and none may enter documentation as though measured (FR-042).
**Scale/Scope**: Single deployment, synthetic data only. Engine A only; Engine B out of scope.
**Constraints**:

- No outbound network call from the assessment path (FR-047, SC-017). Verified with egress blocked.
- `LLM_ENABLED` resolved at call time, never at import (Principle IV, FR-044).
- `mypy --strict` on `src/domain/` and `src/engines/`.
- Agent layer uses `Agent.as_tool()` composition only. `handoff()` is prohibited — it transfers
  control, which is how an agent would come to route a judgment. No tool wraps an engine call; the
  import contract makes that unrepresentable rather than merely discouraged.
- OpenAI Agents SDK tracing MUST be disabled (`set_tracing_disabled(True)`). It exports to a third
  party by default; the clinical audit trail belongs in `run_manifests` and `narratives` in our own
  Postgres.

### Stack divergences from `HARNESS.md` Part IX

Two divergences existed when this plan was written, both recorded rather than silently taken.
Neither weakened a principle, and both are now **resolved**. `HARNESS.md` was amended on 2026-08-23 (v1.0 → v1.1, with an amendment
log), and the constitution followed in the same change (v1.0.0 → v1.0.1, PATCH).

| Item | `HARNESS.md` IX.1 said | Now | Authority |
|---|---|---|---|
| Agent orchestration | LangGraph | OpenAI Agents SDK, `as_tool()` only, `handoff()` prohibited, tracing off | **ADR-0005**, in force |
| LLM sampling settings | `temperature=0`, seed where supported | Removed — not settable on the pinned model | ADR-0004 |
| Layer name | `ai/graph` | `ai/orchestration` (IV.8, IV.11, IX.7, and the constitution's contract table) | ADR-0005 |

Determinism of the LLM layer was never claimed — it is covered by narrative refusal and omission
rates, not reproducibility — so the settings amendment removed a setting, not a guarantee. In its
place, **schema parse-failure rate is now a measured metric**: the OpenAI-compatible layer does not
guarantee schema conformance and ignores the `strict` parameter for function calling, so the gap is
measured beside the refusal and omission rates rather than assumed away. If it proves material the
narrative agents move to the native provider SDK behind the same `LlmClient` protocol, with no
change above that protocol.

## Constitution Check

Evaluated against constitution v1.0.1. Every principle names an owning test file, and every owning
test file is a deliverable of the phase that closes it — not follow-up work. An invariant that
exists only as prose is not enforced.

| # | Principle | Enforcement mechanism in this plan | Owning test file | Closed in |
|---|---|---|---|---|
| I | Engine holds all clinical authority | `import-linter` contract over `src/`; adjudicator deleted | `tests/invariants/test_llm_authority.py` | Phase 0 (contract), Phase 5 (deletion) |
| II | Unknown is first-class and halts | Discriminated `PhenotypeCall` union; `phenotype_calls` CHECK constraint | `tests/invariants/test_unknown_halts.py` | Phase 2 |
| III | Every recommended drug assessed for this patient | `AlternativeSet` constructible only from `Assessment`; `indication` required | `tests/invariants/test_alternatives_assessed.py` | Phase 3 |
| IV | Fully functional with the LLM disabled | `llm-disabled` CI job; call-time flag resolution | `tests/invariants/test_llm_disabled.py` | Phase 0 (switch), Phase 7 (full ablation) |
| V | Every clinical claim carries provenance | Fail-closed policy loader; renderer refuses unprovenanced fields | `tests/invariants/test_provenance.py` | Phase 5, Phase 6 |
| VI | Over-flagging is a tracked failure | `concordance` and `alert-burden` CI jobs; committed JSON scorecards | `tests/invariants/test_alert_burden.py` | Phase 1 (metric), Phase 8 (tiering) |
| VII | Server state never read from the client | Endpoints take identifiers; gate state is a fold; `assessment_sha256` binding | `tests/invariants/test_server_owned_state.py` | Phase 4 |
| VIII | Citations verified against the pinned corpus | `src/ai/gate.py`, plain Python; `narratives` records verdict per attempt | `tests/invariants/test_grounding_gate.py` | Phase 6 |
| IX | Input contradictions halt | `ProfileValidator` raises on conflicting sources | `tests/invariants/test_input_contradiction.py` | Phase 2 |
| X | Review gate is not a safety control | Basis-first ordering; two-sided override alarms; documentation scan | `tests/invariants/test_review_gate_posture.py` | Phase 4 (state machine), Phase 8 (interface) |

### Gate evaluation

**PASS.** The two amendments this plan depended on landed on 2026-08-23; five open decisions are
carried forward, one of them external.

No principle is violated by this plan. Three points need stating plainly:

1. **The tree is non-compliant today and the plan does not pretend otherwise.** The constitution
   ratified a standard the current code fails on Principles I, IV, V, VI, VII and determinism. The
   plan closes them in Delivery Order; until a phase lands, its principle stays recorded as
   non-compliant. Ratification records the standard, not conformance to it.
2. **Principle IV has an unnumbered prerequisite that comes before Delivery step 1.** The
   constitution states it directly: the ablation switch must actually work and the engine must make
   no network calls, or step 1 measures a non-deterministic, covertly LLM-assisted engine and
   reports the result as fact. That is Phase 0, ahead of measurement.
3. **Principle V ships knowingly provisional.** No pharmacist has signed the severity policy table.
   Every row loads as `provisional` and every assessment touching one is flagged. This is the
   constitution's prescribed behaviour, not a shortcut — provisional rows may ship, they may not be
   hidden.

### Complexity tracking

| Added complexity | Why it is necessary | Simpler alternative rejected because |
|---|---|---|
| A second service (PharmCAT over HTTP) | Reference implementation from the consortium that publishes the guidelines | Maintaining a hand-copied slice of CPIC in-process is the audited defect that produced 46% concordance |
| An agent framework rather than plain async calls | `as_tool()` composition, typed `output_type`, per-agent model pinning | Plain async was ADR-0004's position; the hand-rolled loop it replaced silently suppressed parallel tool calls and regexed JSON out of prose. Superseded by ADR-0005 |
| Two source trees during Phases 1–7 | Delivery step 1 must measure the outgoing engine to produce the "before" figure | Deleting legacy first destroys the baseline and makes the improvement asserted rather than demonstrated |
| `testcontainers` rather than a mocked database | Silent write failures passing CI is a catalogued failure pattern | A mock cannot exercise the `CHECK` constraint or the generated `provisional` column, which are the enforcement mechanisms for Principles II and V |

## Project Structure

### Documentation (this feature)

```
specs/001-pgx-safety-harness/
├── spec.md              # 64 FRs, 18 SCs, 10 prioritised stories
├── plan.md              # this file
├── research.md          # Phase 0 findings; open decisions and their disposition
├── data-model.md        # domain types, database schema, gate state machine
├── quickstart.md        # how to run, measure, and verify the invariants locally
├── contracts/
│   ├── openapi.yaml     # the v1 API surface — every endpoint takes identifiers
│   └── README.md        # contract propagation rules and generation commands
└── checklists/
    └── requirements.md
```

### Source code (repository root)

```
agent-server/
  src/
    domain/                 # pure types · ZERO internal imports · mypy strict
      provenance.py         #   ToolResult, Provenanced[T], Citation
      genes.py              #   Gene, VocabularyClass, ALLOWED_TERMS (built from CPIC tables)
      phenotype.py          #   KnownPhenotype | UnknownPhenotype (discriminated)
      drugs.py              #   DrugCode, Indication, Formulary
      assessment.py         #   Outcome, Severity, Finding, Assessment, AlternativeSet
      gate.py               #   GateState, GateTransition
      errors.py             #   HaltReason, EngineError, WriteError
    engines/                # deterministic judgment · MUST NOT import ai/ · mypy strict
      pgx/
        pharmcat/           #   adapter.py · outside_calls.py · parse.py
        severity.py         #   fail-closed policy loader + (gene, phenotype, drug) lookup
        alternatives.py     #   safe_alternatives(profile, drug, indication)
        assess.py           #   assess(profile, drug) — the total function
    evidence/               # retrieval only · no judgment
      corpus.py             #   snapshot ingestion and pinning
      retrieval.py          #   tsvector + pgvector + reciprocal-rank fusion
    ai/                     # ALL model-touching code
      client.py             #   LlmClient protocol — the only provider seam
      agents/               #   intake · evidence · explain · qa · coverage
      gate.py               #   the grounding gate — plain Python, never a model
      templates/            #   deterministic narrative fallbacks (Principle IV)
      orchestration/        #   run assembly, Agents SDK wiring, tracing disabled, budgets
    platform/
      db/                   #   psycopg3 pool · repositories · alembic migrations
      auth/                 #   authn · authz · gate state machine
      audit/
      telemetry/
    api/
      routes/
      deps.py
  policy/severity/          # one reviewed YAML per gene
  tools/registry.yaml       # pinned tool versions, image digests, licences
  eval/                     # golden set, concordance harness, committed scorecards
  tests/
    invariants/             # one file per principle — see the Constitution Check table
    contract/               # OpenAPI conformance
    integration/            # testcontainers-backed
    unit/
  # legacy tree — measured in Phase 1, deleted in Phase 8:
  main.py  agents/  pgx/  mcps/  fhir/  db/  knowledge/  models.py  …

web/
  src/
    lib/                    # api.ts, generated types, generated zod schemas
    components/
    app/
```

**Structure decision**: web application, two deployable units. The backend adopts the `HARNESS.md`
IV.8 topology verbatim under `agent-server/src/`, because the import contract is written against
those exact package names and is what makes Principle I mechanical rather than aspirational. The
legacy tree stays in place, outside the contract, until Phase 8 — it is the only thing that can
produce the "before" figure.

## Phases

Sequenced by the constitution's Delivery Order. Reordering requires a constitutional amendment.
Each phase names its owning test files as deliverables.

### Phase 0 — Prerequisites (before Delivery step 1)

The constitution names these as an unnumbered prerequisite to steps 1 and 2. Measuring an engine
that can reach the network, or covertly reach a model, produces a number that is not a fact.

| ID | Deliverable |
|---|---|
| ~~P0-1~~ | **Done 2026-08-23.** `HARNESS.md` IX.1 (orchestration, settings), IX.6 (pin list), the MANIFEST AI-layer table, and `ai/graph` → `ai/orchestration` in IV.8/IV.11/IX.7; constitution v1.0.1 with the matching pin sentence and contract-table rename |
| ~~P0-2~~ | **Done 2026-08-23.** `docs/adr/0005-agent-framework.md`, in force, including the measured schema parse-failure clause |
| P0-3 | `LLM_ENABLED` resolved at call time; the import-time provider client in the legacy tree neutralised so the switch is real in every environment (FR-043, FR-044) |
| P0-4 | Remove the live RxNorm HTTP call from the assessment path; a local versioned lexicon snapshot replaces it (FR-047) |
| P0-5 | `src/` skeleton plus `.importlinter` contract and the `import-linter` CI job — the contract exists before there is code to violate it |
| P0-6 | CI jobs `lint`, `typecheck`, `contracts` wired; the remaining jobs are added by the phase that makes each meaningful |

**Owning tests**: `tests/invariants/test_llm_authority.py` (contract half); a first
`tests/invariants/test_llm_disabled.py` asserting the switch resolves at call time; an
egress-blocked test asserting no outbound call from the assessment path.

### Phase 1 — Measurement (Delivery step 1) · User Story 1 · P1

Produces the baseline. **The reference concordance harness supplied by the project owner is the
starting shape for this phase — it is adapted, not redesigned.**

| ID | Deliverable |
|---|---|
| P1-1 | Adopt the supplied harness into `eval/`, keeping its scoring semantics |
| P1-1a | Add the CYP2D6 VCF companion case required by ADR-0007, so the structural-variant gap appears in the scorecard rather than only in prose |
| P1-2 | Golden set transcribed from CPIC published tables with provenance per row, never generated from system output (FR-035); human-only verification attestation (FR-035a) |
| P1-3 | Scorecard: agreement, false negative rate, false positive rate, alert burden, halt rate, each broken down per gene and per drug class. Aggregate-only reporting is prohibited (FR-036, FR-037) |
| P1-4 | Two-stage agreement reported separately — genotype→phenotype, and phenotype+drug→recommendation (FR-036a) |
| P1-5 | Baseline run against the **outgoing** implementation, twice: `LLM_ENABLED=false` and `LLM_ENABLED=true`. Both figures committed as dated JSON |
| P1-6 | CI jobs `concordance` and `alert-burden` with floors; a regression names the specific rows that moved |

**Owning tests**: `tests/invariants/test_alert_burden.py`; a determinism check (same input and seed →
identical scorecard).

**Exit criterion**: a committed, dated, reproducible baseline scorecard. Everything after this is
measured against it.

### Phase 2 — Typed phenotype, unknown halts (Delivery step 2) · User Story 2 · P1

| ID | Deliverable |
|---|---|
| P2-1 | `domain/phenotype.py`: `KnownPhenotype \| UnknownPhenotype` with `Field(discriminator="kind")` and no default branch |
| P2-2 | `ALLOWED_TERMS` built from CPIC gene definition tables at build time, never hand-typed |
| P2-3 | `GenomicProfile.calls` covers every in-scope gene; uncovered genes present as `UnknownPhenotype(reason="assay_does_not_cover")`, never absent |
| P2-4 | `Outcome` (StrEnum) and `Severity` (IntEnum) disjoint; no operation accepts both |
| P2-5 | `phenotype_calls` table with `CHECK ((kind='known') = (term IS NOT NULL))` |
| P2-6 | `ProfileValidator` halts on contradictory sources, naming both (FR-031) |
| P2-7 | FHIR and external import record unmapped genes as explicit unknowns preserving the original text (ADR-0003, FR-033a/b) |

**Owning tests**: `tests/invariants/test_unknown_halts.py`,
`tests/invariants/test_input_contradiction.py`; Hypothesis property tests over each phenotype
vocabulary.

**Expected effect on the scorecard**: halt rate jumps sharply. Per the constitution and SC-015 this
is recorded as previously hidden gaps becoming visible, and MUST NOT be treated as a regression.

### Phase 3 — Alternatives re-assessed for this patient (Delivery step 3) · User Story 3 · P1

| ID | Deliverable |
|---|---|
| P3-1 | `AlternativeSet` constructible only from `Assessment` objects — the defect becomes unrepresentable |
| P3-2 | `safe_alternatives()` requires `indication`; a value outside the curated list is refused, not interpreted (ADR-0001) |
| P3-3 | `NoSafeAlternative` as a first-class result carrying its `considered` set |
| P3-4 | `alternatives_considered` always written, rejects included with the reason for each |
| P3-5 | The six reproduced audit cases become named permanent regression tests |

**Owning test**: `tests/invariants/test_alternatives_assessed.py`.

### Phase 4 — Server-owned gate state (Delivery step 4) · User Story 4 · P1

| ID | Deliverable |
|---|---|
| P4-1 | `gate_transitions` append-only; current state is the fold; no updatable status column exists |
| P4-2 | `assessment_sha256` content binding; approval auto-transitions to `SUPERSEDED` when content changes |
| P4-3 | `POST /v1/reports` accepts `{evaluation_id}` only — loads server-side, folds, re-verifies the hash |
| P4-4 | The transition endpoint requires `assessment_sha256`, giving content binding and optimistic concurrency in one move |
| P4-5 | Role model; `PHARMACIST` is the only role that may approve; `require_access()` on every patient-scoped route |
| P4-6 | The forged-body case becomes a permanent regression test |

**Owning tests**: `tests/invariants/test_server_owned_state.py`;
`tests/invariants/test_review_gate_posture.py` (state-machine half).

**Steps 1–4 remove most of the clinical risk. If nothing else ships, ship those.**

### Phase 5 — PharmCAT, severity policy, adjudicator deleted (Delivery steps 5–7) · P2

| ID | Deliverable |
|---|---|
| P5-1 | `ToolAdapter` ABC recording tool name, version, image digest, input and output SHA-256, parameters |
| P5-2 | PharmCAT as a pinned image behind a thin HTTP wrapper; outside-call path for fixtures and FHIR; entry at the phenotyper |
| P5-3 | Result cache keyed on `(image_digest, input_sha256, parameters)` |
| P5-4 | `policy/severity/*.yaml` per gene; loader fails closed on any row missing provenance or a reviewer; `provisional` a generated column |
| P5-5 | An absent `(gene, phenotype, drug)` triple yields `NO_GUIDANCE`, never `low` |
| P5-6 | Delete the LLM adjudicator; the engine is authoritative |
| P5-7 | Re-measure in the same change — the constitution requires it for any PharmCAT or policy version bump |

| P5-8 | Acceptance check *before* the adapter is written: feed `*1/*2x2` through PharmCAT's outside-call path and confirm the Phenotyper returns ultrarapid (ADR-0007) |
| P5-9 | Second caller (PyPGx, StellarPGx as fallback) for CYP2D6 on the **VCF path only**, behind the same `ToolAdapter` interface (ADR-0007) |

**Owning tests**: `tests/invariants/test_provenance.py`; `tests/invariants/test_llm_authority.py`
(deletion half). **Blocked on** the licence half of open decision 3 — PharmCAT's terms, and now
PyPGx's. The coverage half is closed by ADR-0007.

### Phase 6 — Grounding gate and evidence (Delivery step 8) · User Stories 6, 7 · P2

| ID | Deliverable |
|---|---|
| P6-1 | Corpus snapshots pinned and immutable; `Citation` stores character offsets, never quoted text (FR-019) |
| P6-2 | Hybrid retrieval: `tsvector` + `pgvector` with RRF in SQL; `fastembed` ONNX CPU embeddings, offline |
| P6-3 | `src/ai/gate.py` — the seven checks, including the undeclared-entity scan against the full local drug lexicon |
| P6-4 | Failure policy: reject → regenerate once with the violation fed back → reject → deterministic template |
| P6-5 | `narratives` records verdict, rejection reasons and attempt number; refusal, omission **and schema parse-failure** rates reported (ADR-0005) |
| P6-6 | Explain, Q&A and Coverage agents via `Agent.as_tool()` with typed `output_type` and tracing disabled |
| P6-7 | Renderer refuses any unprovenanced clinical claim (FR-014) |

**Owning test**: `tests/invariants/test_grounding_gate.py`.

### Phase 7 — Ablation and determinism · User Story 9 · P3

| ID | Deliverable |
|---|---|
| P7-1 | `llm-disabled` CI job runs the complete suite with `LLM_ENABLED=false` |
| P7-2 | Verdict, findings and alternatives identical between the enabled and disabled runs |
| P7-3 | `determinism` CI job: same input and seed → identical engine output |
| P7-4 | `RunManifest` records every pin that can affect output |
| P7-5 | The ablation comparison is published **even if the model layer does not beat the deterministic baseline** |

**Owning test**: `tests/invariants/test_llm_disabled.py` (complete).

### Phase 8 — Review interface, authorization, data layer, deletions (Delivery steps 9–13) · P2/P3

| ID | Deliverable |
|---|---|
| P8-1 | Basis-first review surface: genotype, guideline text and citation before the severity label |
| P8-2 | The `considered` set always shown; provisional findings visually distinct |
| P8-3 | Override-rate monitoring with alarms at both ends (~90% fatigue, ~5% automation bias) |
| P8-4 | `care_team_assignments` plus `require_access()`; a single JWT validation path checking expiry, audience and issuer |
| P8-5 | psycopg3 async pool; in-memory fallback dictionaries replaced by an explicit flagged degraded mode |
| P8-6 | Alert tiering by severity; `HALTED` interrupts but is framed as missing data |
| P8-7 | Delete the therapy slice, MisuseMonitor, CostNavigator, the MCP stdio layer, and the legacy tree |
| P8-8 | `openapi-typescript` plus generated Zod schemas, committed; drift becomes a failing build |

**Owning test**: `tests/invariants/test_review_gate_posture.py` (complete), including a documentation
scan asserting that no artifact claims human review as mitigation for engine error.

### Phase 9 — Re-measure and correct the record (Delivery step 14) · P3

| ID | Deliverable |
|---|---|
| P9-1 | Full re-measurement against the golden set; scorecard committed and dated |
| P9-2 | `README.md`, `PITCH_DECK.md` and `CONCORDANCE_MEMO.md` corrected — every figure measured and dated, or labelled an estimate |
| P9-3 | The research-only, not-a-medical-device statement on every surface, at the API root, and in every generated document footer |
| P9-4 | Alert burden, narrative refusal rate, omission rate, schema parse-failure rate and override rate published for the release |

## Target CI pipeline

`lint` · `typecheck` (mypy strict on `src/domain/` and `src/engines/`) · `test` · `invariants` (ten
files, one per principle) · `llm-disabled` · `concordance` · `alert-burden` · `determinism` ·
`contracts` · `frontend`.

CI today runs two jobs. Each phase above adds the jobs it makes meaningful, and no job is deferred
past the phase that closes its principle.

## Open decisions carried into implementation

Recorded, not picked. Full disposition in [research.md](./research.md).

| # | Decision | Blocks | Status |
|---|---|---|---|
| 1 | Named clinical reviewer for the severity table | Any non-provisional clinical claim | **Open — external dependency** |
| 2 | Criterion 1 IVD boundary | Non-research positioning only | Open |
| 3a | PharmCAT licence terms | Phase 5 | **Open — blocking.** Now covers PyPGx's licence too |
| 3b | PharmCAT gene coverage | — | **Closed — ADR-0007.** Second caller for CYP2D6, VCF path only |
| 6 | Severity scale | — | **Closed — ADR-0006.** Four levels retained |
| 8 | Engine B timing and reviewer | Nothing in this feature | Open, out of scope |
| 9 | pgvector on the chosen managed Postgres | Phase 6 deployment, not the build | Open; dev and CI use `pgvector/pgvector:pg16` |
| 10 | Structured-output support for the pinned model | Phase 6 | **Answered by measurement rather than assertion** — schema parse-failure rate is a reported metric (ADR-0005) |
| 11 | Host capability for a second service | Deployment | **Open — should drive the hosting choice, not follow it.** Two services beyond the app if the VCF path ships |

Closed to date: 4 (ADR-0002), 5 (ADR-0001), 7 (ADR-0003), agent framework (ADR-0005), severity scale
(ADR-0006), PharmCAT coverage (ADR-0007). Five remain open, one of them — the clinical reviewer —
external.

---

*Research and education only. Synthetic data only. Not a medical device.*
