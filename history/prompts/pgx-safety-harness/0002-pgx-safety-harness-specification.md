---
id: 0002
title: PGx Safety Harness Specification
stage: spec
date: 2026-08-21
surface: claude-code
model: claude-opus-5
feature: pgx-safety-harness
branch: 001-pgx-safety-harness
route: history/prompts/pgx-safety-harness/
artifacts:
  - specs/001-pgx-safety-harness/spec.md
  - specs/001-pgx-safety-harness/checklists/requirements.md
derived_from: .specify/memory/constitution.md v1.0.0
status: superseded by PHR 0003 — all 3 questions resolved, checklist fully passing
links:
  - .specify/memory/constitution.md
  - HARNESS (1).md
  - history/prompts/constitution/0001-harness-derived-project-constitution.md
---

# PHR 0002 — PGx Safety Harness Specification

## Stage

`spec` — feature specification for branch `001-pgx-safety-harness`, derived from constitution v1.0.0.

## Prompt (verbatim)

```text
based on current constitution create a comprehensive specification
```

Invoked via `/sp.specify`, whose outline directs: generate a short name, check all three sources for
the highest existing feature number, run `create-new-feature`, load `spec-template.md`, write the
spec, generate and run a quality checklist, resolve or escalate `[NEEDS CLARIFICATION]` markers to a
maximum of three, and record a PHR.

## Context

Constitution v1.0.0 was ratified earlier the same day from `HARNESS (1).md`. It establishes ten
binding principles and explicitly records that the current tree violates six of them. This
specification is the feature-level expression of closing that gap.

Branch numbering: `git fetch --all --prune` succeeded for `origin` and failed for the `hf` remote
(repository not found). No local branch, remote branch, or `specs/` directory matched
`[0-9]+-pgx-safety-harness`, so the feature is number **001**.

## Deviations from the command outline

Spec-kit scaffolding is still absent from this repository, so two steps used fallbacks:

1. **`create-new-feature` script unavailable.** `.specify/scripts/powershell/create-new-feature.ps1`
   does not exist, nor does a bash equivalent. The branch `001-pgx-safety-harness` was created with
   `git checkout -b` and the `specs/001-pgx-safety-harness/` tree created directly. The uncommitted
   changes already present on `main` carried over to the new branch, as git does by default; nothing
   was committed or discarded.

2. **`spec-template.md` unavailable.** The spec was written to the standard spec-kit section
   structure — Overview, User Scenarios & Testing with prioritised stories, Edge Cases, Requirements
   with Functional Requirements and Key Entities, Success Criteria, Assumptions, Dependencies —
   preserving section order and heading levels.

The PHR script was likewise unavailable, so this record was written directly per the documented
fallback. ID `0002` follows `0001` (the constitution PHR).

## Response summary

Created `specs/001-pgx-safety-harness/spec.md` and its quality checklist.

**Shape**: 10 prioritised user stories, 11 edge cases, 60 functional requirements in 11 groups, 14
key entities, 18 measurable success criteria, plus Assumptions, Dependencies, and Open Questions.

**Priority ordering follows the constitution's Delivery Order**, which ranks by clinical risk removed
per unit of work rather than by build convenience:

| Priority | Stories | Rationale |
|---|---|---|
| P1 | 1 Honest measurement · 2 Missing data halts · 3 Alternatives checked for this patient · 4 Approval binds to what was reviewed | The constitution's "if nothing else ships, ship those" |
| P2 | 5 Basis before verdict · 6 Provenance on every claim · 7 Narrative bounded by the assessment | Regulatory criterion 4 and the grounding gate |
| P3 | 8 Coverage reporting · 9 Works with the model off · 10 Alert tiering | Depends on P1/P2 being correct first |

**Non-obvious drafting decisions:**

- **Every principle was translated into observable behaviour rather than restated.** The constitution
  is architectural by nature — import contracts, discriminated unions, content hashes — none of which
  belongs in a spec written for stakeholders. Principle II became "missing genetic data stops the
  assessment"; Principle VII became "an approval covers only what was actually reviewed." The
  mechanism moves to `/sp.plan`; the spec states what a tester can observe.
- **Story 1 is P1 despite producing no user-facing capability.** The constitution forbids promoting
  an unmeasured oracle to authority, so every other story's correctness claim is unverifiable until
  measurement exists.
- **Story 9 (model disabled) is P3 rather than P1**, though the constitution treats it as
  foundational. Rationale: it is a property the P1 work must preserve, not a separate deliverable —
  but FR-044 specifically requires the setting to resolve at time of use rather than process start,
  because the existing switch is evaluated at import and is therefore inert in tests.
- **SC-015 pre-empts a misreading.** Halt rate will rise sharply when explicit unknowns land. The
  criterion records this as hidden gaps becoming visible, so the improvement is not reported as a
  regression.
- **Success criteria carry measured starting points where they exist** — SC-002 names the 29%
  false-positive baseline — so progress is verifiable rather than asserted.

**Checklist result: 15 of 16 items pass.** The single failure is deliberate and is explained in the
checklist notes: exactly three `[NEEDS CLARIFICATION]` markers remain, at the permitted limit. The
constitution's governance section forbids picking its open decisions silently and calls doing so in
code a governance violation, so defaulting them to clear the checklist would violate the document the
spec derives from.

The three escalated questions are indication vocabulary, guideline source precedence, and external
record import scope — selected from the constitution's eleven open decisions by scope and safety
impact. Severity scale was defaulted to the existing four levels and recorded in Assumptions as
pending an architecture decision rather than escalated.

## Incidental finding

`git remote -v` exposes a HuggingFace access token embedded in plaintext in the `hf` remote URL in
`.git/config`. The remote returns "repository not found", so the target may be gone, but the token
itself is readable by anything that can run `git remote -v` and would travel with any copy of the
repository configuration. Raised to the user; not acted on, since rotating or removing a credential
is the user's call.

## Follow-up

- Answer the three open questions, then re-run validation to close the checklist.
- Proceed to `/sp.clarify` or `/sp.plan`.
- Record each answered decision as an architecture decision record. `docs/adr/` does not yet exist.
- Spec-kit scaffolding remains uninstalled; `specify init --here` would overwrite the constitution
  unless it is backed up first.

## Suggested commit message

```
docs: add feature spec 001 for constitution-conformant PGx harness
```
