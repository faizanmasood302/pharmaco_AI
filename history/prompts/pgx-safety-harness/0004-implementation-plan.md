---
id: 0004
title: Implementation Plan For Rebuild
stage: plan
date: 2026-08-23
surface: claude-code
model: claude-opus-5
feature: pgx-safety-harness
branch: 001-pgx-safety-harness
route: history/prompts/pgx-safety-harness/
artifacts:
  - specs/001-pgx-safety-harness/plan.md
  - specs/001-pgx-safety-harness/research.md
  - specs/001-pgx-safety-harness/data-model.md
  - specs/001-pgx-safety-harness/contracts/openapi.yaml
  - specs/001-pgx-safety-harness/contracts/README.md
  - specs/001-pgx-safety-harness/quickstart.md
  - docs/adr/0005-agent-framework.md
  - CLAUDE.md
status: superseded by PHR 0005 — the two pending amendments landed 2026-08-23
links:
  - .specify/memory/constitution.md
  - specs/001-pgx-safety-harness/spec.md
  - docs/adr/0004-llm-provider-and-sdk.md
  - history/prompts/pgx-safety-harness/0003-resolve-spec-open-questions.md
---

# PHR 0004 — Implementation Plan For Rebuild

## Stage

`plan` — turning the 64 functional requirements of spec 001 into a phased build order with design
artifacts.

## Prompt (verbatim)

```text
Implement per the constitution v1.0.0 and spec 001. Technology constraints are fixed in HARNESS.md Part IX — read it and follow it rather than re-deriving choices.

Key stack decisions, already made:

Python 3.12, uv, Pydantic v2, FastAPI, mypy strict on domain/ and engines/
import-linter enforces the layer contract in the constitution's Architectural Constraints table. This is how Principle I is enforced — it is not optional
PostgreSQL 16 with pgvector and tsvector. No separate vector service
psycopg3 async pool. Not per-query connections
PharmCAT as a separate pinned service reached over HTTP, not a subprocess
OpenAI Agents SDK for the agent layer, with Agent.as_tool() only. handoff() is prohibited. No tool may wrap an engine call
testcontainers for real Postgres in tests. Do not mock the database

Sequence the plan to follow the constitution's Delivery Order. User Story 1 (measurement) comes first and produces a baseline figure from the outgoing implementation before any replacement work begins.

A reference implementation of the concordance harness exists and I will provide it — treat it as the starting shape for User Story 1, not as something to redesign.

Every principle in the constitution names an owning test file. Plan those test files as deliverables, not as follow-up work. An invariant that exists only as prose is not enforced.
```

## Context

Feature 001 is a rebuild, not a remediation (PHR 0003). The constitution ratified a standard the
current tree fails on six of ten principles. The spec was left at "Ready for planning" with three
decisions resolved as ADR-0001 through ADR-0003 and eight of `HARNESS.md` Part XI's eleven open
decisions still open.

`HARNESS (1).md` has since been renamed `HARNESS.md`; the stale references in `CLAUDE.md` were
corrected as part of this change.

## Response

### Artifacts produced

- **`plan.md`** — Technical Context, Constitution Check with a per-principle enforcement table,
  Complexity Tracking, project structure, ten phases (0–9) sequenced by the constitution's Delivery
  Order, the target CI pipeline, and the open decisions carried into implementation.
- **`research.md`** — the two stack divergences and their disposition, all eleven open decisions
  with status and blocking effect, four technical findings the plan depends on, and an explicit note
  on what was deliberately *not* researched because the stack was fixed in advance.
- **`data-model.md`** — the two type-level decisions that carry the safety argument (the
  discriminated `PhenotypeCall`, and `Outcome`/`Severity` disjointness), all key entities, the
  PostgreSQL schema, the gate state machine, the halt-propagation table, and a
  validation-rule-to-requirement map.
- **`contracts/openapi.yaml`** — thirteen endpoints matching `HARNESS.md` IV.10, twenty-four
  schemas, `additionalProperties: false` on every request body. Parses clean.
- **`contracts/README.md`** — contract propagation direction, generation commands, and the
  `contracts` CI job checklist.
- **`quickstart.md`** — commands, the measurement workflow with guidance on reading the numbers, and
  a per-principle table of what to run to verify each invariant by hand.
- **`docs/adr/0005-agent-framework.md`** — the agent-framework decision, recorded rather than taken
  silently.
- **`CLAUDE.md`** — an "Active feature" section (agent-context update, done by hand; see Deviations).

### The divergence that had to be resolved rather than absorbed

Three sources disagreed on the agent layer, all three still live:

| Source | Position |
|---|---|
| `HARNESS.md` IX.1 | LangGraph |
| ADR-0004 (2026-08-22) | No orchestration framework; plain async Python |
| This plan input | OpenAI Agents SDK, `as_tool()` only |

The prompt said to follow Part IX "rather than re-deriving choices" and then named a different
framework, so the two instructions could not both be followed literally. Resolved in favour of the
later and more specific instruction, and recorded as ADR-0005 rather than absorbed into the plan —
the constitution makes picking one of these implicitly, in code, a governance violation.

The three named restrictions turned out to be constitution-reinforcing rather than merely stylistic,
and the ADR argues them on that basis: `handoff()` transfers control of a run, which is precisely
how a judgment would migrate into the agent layer; `as_tool()` returns control after each call. A
fourth restriction was added that the prompt did not name — **SDK tracing must be disabled** — on
the grounds that it exports to a third party by default, which would reintroduce exactly what
ADR-0004 removed when it deleted LangSmith.

The provider decision from ADR-0004 is unchanged: Anthropic `claude-opus-5` behind the `LlmClient`
protocol, reached through the SDK's LiteLLM extension. Verified against the Agents SDK reference
that `LitellmModel`/`LitellmProvider` exist for exactly this, rather than assuming it.

### Second divergence, already known

`HARNESS.md` IX.1 specifies `temperature=0, seed where supported`, and IX.6 pins both in
`RunManifest`. Neither is settable on the pinned model. ADR-0004 already recorded this; the plan
groups it with the ADR-0005 amendment as **P0-1**, since both edit the same two tables.

### Constitution Check

**PASS**, with two recorded amendments and eight open decisions carried forward. Three things were
stated rather than smoothed over: the tree is non-compliant today and the plan does not pretend
otherwise; Principle IV has an unnumbered prerequisite that sits *before* Delivery step 1, so the
ablation switch and the network removal are Phase 0; and Principle V ships knowingly provisional
because no pharmacist has signed the severity table.

All ten owning test files are phase deliverables, per the prompt's closing instruction. The
Constitution Check table names each file and the phase that closes it.

## Deviations

Spec-kit per-project scaffolding is still absent — no `.specify/scripts/`, no `.specify/templates/`.
Three documented fallbacks were used, the same ones recorded in PHRs 0002 and 0003:

1. `setup-plan.ps1` does not exist. Branch, spec path and plan path were resolved directly from the
   repository; the plan was written to the conventional location.
2. `update-agent-context.ps1` does not exist. `CLAUDE.md` was updated by hand, additively — an
   "Active feature" section was inserted and the stale `HARNESS (1).md` references corrected. No
   existing content was removed.
3. `create-phr.sh` does not exist. This file was written directly, with the ID allocated by
   inspecting the directory.

## Follow-ups

1. ~~**P0-1 needs owner sign-off before implementation.**~~ **Done 2026-08-23** — see PHR 0005.
   `HARNESS.md` is at v1.1, the constitution at v1.0.1, and ADR-0005 is in force.
2. **The reference concordance harness has not been supplied yet.** Phase 1 is written around
   adapting it rather than designing one; it is the phase's first input. *(Still outstanding as of
   PHR 0005 — reported present at `eval/`, but no such directory exists in the tree.)*
3. **`/sp.tasks`** is the next spec-kit step.
4. Open decisions 3 (PharmCAT licence and coverage) and 6 (severity scale) both land on Phase 5 and
   are cheapest to settle together, before it starts.
5. Open decision 1 — the named clinical reviewer — remains a blocking external dependency. Until a
   pharmacist signs the severity table, every row is provisional.
6. Nothing is committed. The plan artifacts join ten uncommitted artifacts from PHRs 0002 and 0003
   plus the `pyproject.toml` / `uv.lock` dependency change.
7. The HuggingFace token embedded in plaintext in the `hf` git remote URL is still unrotated.

## Suggested commit

```text
docs: add implementation plan for feature 001; record ADR-0005
```
