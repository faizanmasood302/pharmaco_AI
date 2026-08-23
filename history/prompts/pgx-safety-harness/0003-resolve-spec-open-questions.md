---
id: 0003
title: Resolve Spec Open Questions
stage: spec
date: 2026-08-21
surface: claude-code
model: claude-opus-5
feature: pgx-safety-harness
branch: 001-pgx-safety-harness
route: history/prompts/pgx-safety-harness/
supersedes: 0002
artifacts:
  - specs/001-pgx-safety-harness/spec.md
  - specs/001-pgx-safety-harness/checklists/requirements.md
  - docs/adr/0001-indication-vocabulary.md
  - docs/adr/0002-guideline-source-precedence.md
  - docs/adr/0003-external-record-import-scope.md
status: complete — checklist 16/16 passing, ready for /sp.plan
links:
  - .specify/memory/constitution.md
  - history/prompts/pgx-safety-harness/0002-pgx-safety-harness-specification.md
---

# PHR 0003 — Resolve Spec Open Questions

## Stage

`spec` — clarification round closing the three open questions raised by PHR 0002.

## Prompt (verbatim)

```text
OKay I think you recommendation are best and we should go with that. also I just wanted to be clear that i am updating the project that is way i am
given you a tasked to build new specs because old one is not trustworthy thats why i am shifting whole thing.
```

Preceded in the same exchange by a request to explain the questions in simpler terms and to define
what "FR" meant, which was answered before the decisions were taken.

## Context

PHR 0002 left three `[NEEDS CLARIFICATION]` markers, at the permitted limit, because the constitution
forbids picking its open decisions silently. The project owner accepted the recommendations and
supplied scope context that had not previously been explicit.

## Decisions taken

| Question | Decision | ADR |
|---|---|---|
| Indication vocabulary | Curated, version-controlled condition list covering the formulary | ADR-0001 |
| Guideline source precedence | CPIC alone determines severity; other sources shown as labelled context only | ADR-0002 |
| External record import scope | Unmapped genes imported as explicit unknowns with original text preserved | ADR-0003 |

**One ambiguity was in the recommendation itself and had to be closed.** For source precedence the
prior turn had said "A or B, definitely not C", which is not a recommendation. Resolved to **A**
(CPIC alone) on the grounds that the constitution declares CPIC the single source of truth and
measures agreement against CPIC specifically; if a second source could also set severity, the
headline agreement figure would become a blend across sources with differing coverage and stop having
one meaning. Since the stated purpose of the rebuild is trustworthy numbers, preserving the metric's
interpretability decided it. This was stated to the owner rather than passed over.

The likely successor — fixed precedence CPIC → DPWG → FDA with per-source measurement — is recorded
in ADR-0002's "Revisit when" rather than left implicit.

## Scope reframing

The owner confirmed the existing implementation is being **replaced because it is not trusted**, not
incrementally corrected. This was not previously explicit and it changes how the spec should read.

Applied:

- **Overview** now states the spec describes a replacement, and that existing behaviour is evidence
  of what went wrong, never precedent for what to keep.
- **Assumptions** records that the outgoing implementation serves as a baseline to improve on and a
  catalogue of failures to regression-test, and that its code is not a reference for correctness.
- **User Story 1** gained the reasoning that the case set and scoring are deliberately engine-
  independent. This resolves a tension the reframing creates: Delivery Order step 1 says "measure the
  current engine honestly", which reads oddly when the engine is being discarded. The resolution is
  that the case set is the durable asset — written against published guideline tables, outliving any
  implementation — and running it once against the outgoing system cheaply produces the "before"
  figure that makes the replacement's improvement demonstrable rather than asserted.

No functional requirement changed because of the reframing. It affects plan sequencing, not scope.

## Spec changes

- FR-010 extended with the curated-list constraint and an explicit refusal for out-of-list values.
- FR-015a added: CPIC sole severity authority; non-CPIC sources as labelled context; no-guidance
  returned even where another source has advice.
- FR-033 split into four. FR-033 keeps the absolute prohibition on inventing values; FR-033a imports
  unmapped genes as explicit unknowns with original text preserved; FR-033b bars an unknown from
  contributing to any verdict and halts dependent assessments; FR-033c refuses unresolvable drug
  names outright rather than near-matching. Drugs are treated more strictly than genes deliberately —
  a wrong drug match is silently wrong, whereas an unknown gene is visibly unknown.
- Two edge cases added for CPIC-only precedence; the unmapped-gene edge case revised from rejection
  to explicit unknown.
- `Open Questions` replaced by `Resolved Decisions` with an ADR table.
- Status moved from `Draft` to `Ready for planning`.

## Validation

Checklist re-run: **16 of 16 items pass**. `Requirements are testable and unambiguous` re-checked
against the four new requirements — each states an observable behaviour with a defined refusal or
halt condition. `/sp.clarify` is not required.

## Follow-up

- `/sp.plan` is the next step.
- Remaining open decisions are unchanged and still listed in the constitution's governance section:
  severity scale, criterion 1 IVD boundary, reference implementation licence and coverage, Engine B
  timing and reviewer, and the named clinical reviewer. The last remains a blocking external
  dependency — until a pharmacist signs the severity table, every row is provisional.
- The HuggingFace token in the `hf` remote URL raised in PHR 0002 is still unrotated.

## Suggested commit message

```
docs: resolve spec 001 open questions; add ADR-0001..0003
```
