---
id: 0001
title: Harness Derived Project Constitution
stage: constitution
date: 2026-08-21
surface: claude-code
model: claude-opus-5
feature: constitution
route: history/prompts/constitution/
source_of_authority: HARNESS (1).md v1.0 (21 Aug 2026)
artifacts:
  - .specify/memory/constitution.md
constitution_version: 1.0.0
bump: initial ratification
links:
  - HARNESS (1).md
  - CLAUDE.md
  - CONCORDANCE_MEMO.md
---

# PHR 0001 — Harness Derived Project Constitution

## Stage

`constitution` — initial ratification of `.specify/memory/constitution.md` at version 1.0.0.

## Prompt (verbatim)

```text
Read the @"..\HARNESS (1).md" file and make a full detailed Constitution
```

Invoked via `/sp.constitution`, which carries the standard outline: load the template at
`.specify/memory/constitution.md`, collect placeholder values, draft the constitution, propagate
consistency across `.specify/templates/*`, prepend a Sync Impact Report, validate, write back, and
record a PHR.

## Context

`HARNESS (1).md` is a 1,204-line architecture specification, version 1.0 dated 21 Aug 2026, derived
from a GenomicLens audit of commit `31e5f88` — which is at or near HEAD. Its Part II declares ten
invariants binding and "enforced by types or tests, not convention." That made Part II the natural
backbone for the Core Principles rather than an invented principle set.

The full document was read (both halves; it exceeds a single read window) before drafting. Repo
state was verified independently rather than taken from the spec's assertions.

## Deviations from the command outline

Two steps could not be executed as written, because the spec-kit scaffolding is not installed in
this repository:

1. **No template to operate on.** The outline states "Do not create a new template; always operate
   on the existing `.specify/memory/constitution.md` file." That file did not exist, nor did
   `.specify/` in any form. A search across the repo found no `*constitution*`, `phr-template*`, or
   `create-phr*` artifact. The file was therefore created at the canonical path using the standard
   spec-kit section structure. This is recorded here rather than passed over silently.

2. **Consistency propagation had no targets.** `.specify/templates/plan-template.md`,
   `spec-template.md`, `tasks-template.md`, and `commands/*.md` do not exist. All four are marked
   `⚠ pending` in the Sync Impact Report with their paths, so the check re-runs correctly once
   spec-kit is initialised.

3. **PHR script fallback used.** `.specify/scripts/bash/create-phr.sh` does not exist, so this
   record was written directly per the documented fallback path, with ID `0001` allocated as the
   first record under `history/prompts/`.

## Response summary

Created `.specify/memory/constitution.md` at **v1.0.0**, ratified 2026-08-21.

**Structure.** Governing Thesis · Core Principles I–X · Regulatory Posture and Scope Boundary ·
Architectural Constraints · Measurement and Quality Gates · Delivery Order · Governance.

**Core Principles** map one-to-one onto HARNESS invariants I1–I10, each rewritten from a table row
into a declarative section with MUST-language rules, a named enforcement mechanism, and a rationale
traced to the numbered Part I finding behind it:

| Principle | Invariant | Traces to |
|---|---|---|
| I — The Engine Holds All Clinical Authority | I1 | F12 |
| II — Unknown Is a First-Class Value That Halts | I2 | Audit CLIN-04/05 |
| III — Every Recommended Drug Is Assessed For This Patient | I3 | Audit CLIN-03 |
| IV — Fully Functional With The LLM Disabled | I4 | F12, IX.0 rule 3 |
| V — Every Clinical Claim Carries Provenance | I5 | F2 |
| VI — Over-Flagging Is A Tracked Failure | I6 | F3, F4, F5 |
| VII — Server State Is Never Read From The Client | I7 | Audit CLIN-01 |
| VIII — Citations Verified Against The Pinned Corpus | I8 | F10, F11 |
| IX — Input Contradictions Halt | I9 | F9 |
| X — The Review Gate Is Not A Safety Control | I10 | F6, F7, F8 |

**Non-obvious drafting decisions:**

- Vague modal verbs were replaced with MUST / MUST NOT throughout, per the outline's requirement
  that principles be declarative and testable.
- Each principle names its enforcement mechanism explicitly, and the second corollary of the
  Governing Thesis states that a principle whose mechanism does not yet exist is recorded as
  non-compliant rather than satisfied. This prevents the constitution from reading as a claim about
  the current code.
- A **Known non-compliance at ratification** clause was added to Governance. The current tree
  violates Principles I, IV, V, VI, VII and the determinism constraint. Ratifying a standard the
  code does not meet is legitimate; implying conformance would not be. The clause also states that
  existing violating code must not be cited as precedent.
- The Delivery Order carries an unnumbered prerequisite ahead of step 1: the `LLM_ENABLED` ablation
  switch must actually work and the engine must make no network calls. Without both, step 1 measures
  a non-deterministic, covertly-LLM-assisted engine and reports the result as fact. This is a
  finding from verifying the code, not a restatement of the spec.
- MisuseMonitor's deletion was carried over with its full reasoning (no guideline backing, disparate
  impact exposure, a category of judgment that should not be model-made) rather than reduced to a
  scope cut.

**Deferred TODOs**, both recorded in the Sync Impact Report:

- `TODO(CLINICAL_REVIEWER)` — HARNESS XI.1. No named pharmacist has signed the severity policy
  table. Until one does, every row is provisional and must be presented as such. This blocks
  Principle V from being fully satisfiable.
- `TODO(ENGINE_B_REVIEWER)` — HARNESS XI.8. Engine B requires a computational biologist, a separate
  signatory from the clinical reviewer.

**Validation:** no unresolved bracket placeholders; version line matches the Sync Impact Report;
all dates ISO 8601; no trailing whitespace.

## Follow-up

- Initialise spec-kit templates, then re-run consistency propagation against the four `⚠ pending`
  paths.
- `README.md` and `PITCH_DECK.md` quote concordance figures above the last measured values in
  `CONCORDANCE_MEMO.md` (46% concordance, 29% false positive rate, marked HISTORICAL). Correcting
  them is governed by Delivery Order step 14 and deliberately not done as part of this amendment.
- Resolve the eleven open decisions into `docs/adr/` as they are settled. `docs/adr/` does not yet
  exist.

## Suggested commit message

```
docs: ratify project constitution v1.0.0 from HARNESS spec
```
