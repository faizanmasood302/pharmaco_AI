# Specification Quality Checklist: Constitution-Conformant Pharmacogenomic Safety Harness

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Iteration 1 — one item failing, deliberately.** Three `[NEEDS CLARIFICATION]` markers remained, at
the permitted limit. Not oversights: the constitution's governance section states that the project's
open decisions "MUST be recorded, never silently picked," and names choosing one implicitly in code a
governance violation. Defaulting them to clear the checklist would have violated the document the
spec derives from. They were escalated to the project owner.

**Iteration 2 — all items pass.** The project owner decided all three on 2026-08-21, and each is
recorded as an architecture decision rather than absorbed silently into the spec:

| Question | Decision | ADR | Spec changes |
|---|---|---|---|
| Indication vocabulary | Curated, version-controlled condition list covering the formulary | [ADR-0001](../../../docs/adr/0001-indication-vocabulary.md) | FR-010 extended |
| Guideline source precedence | CPIC alone sets severity; other sources shown as labelled context only | [ADR-0002](../../../docs/adr/0002-guideline-source-precedence.md) | FR-015a added; two edge cases added |
| External record import scope | Unmapped genes imported as explicit unknowns, original text preserved | [ADR-0003](../../../docs/adr/0003-external-record-import-scope.md) | FR-033 split into FR-033/033a/033b/033c; edge case revised |

The `Requirements are testable and unambiguous` item was re-checked after these edits and still
passes: each new requirement states an observable behaviour with a defined refusal or halt condition.

**Scope reframing applied in iteration 2.** The project owner confirmed the existing implementation
is being **replaced, not remediated**, because it is not trusted. The Overview and Assumptions now
state this explicitly, and User Story 1 records why the case set and scoring are deliberately
independent of any particular engine — they are the durable asset, and running them against the
outgoing implementation once yields the "before" figure. No requirement changed as a result; the
framing changed, which affects how the plan should sequence work.

**Content Quality note.** Three requirements sit close to the implementation line and were reviewed
individually rather than waved through: FR-013 records "pinned image identity" for a produced value,
FR-040 and SC-007 refer to a run "seed", and FR-047 forbids "outbound network calls" from the
assessment path. Each is retained because it states an observable property that a tester can verify
without knowing how the system is built — provenance is recorded, repeat runs match, no external
traffic occurs. None names a language, framework, product, or interface.

**Scope note.** The spec covers Engine A only. The mRNA design engine described in the source
architecture is excluded and stated as such in Assumptions.

**Dependency note.** The named clinical reviewer is a blocking external dependency, not a task.
Until one is appointed, every severity policy row is provisional and the system must present it that
way. No planning work can discharge this.

**Status**: All 16 items pass. Ready for `/sp.plan`. `/sp.clarify` is not required — the three
decisions it would have surfaced are resolved and recorded.
