# ADR-0003: Unmapped genes are imported as explicit unknowns

**Status**: Accepted
**Date**: 2026-08-21
**Decider**: M. Faizan (project owner)
**Constitution reference**: Governance — open decisions; Principles II, V and IX
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-033, FR-033a, FR-033b, FR-033c,
User Story 2, SC-015

## Context

Patient records arriving from external systems contain gene results the system may not recognise —
a gene outside its scope, a gene with no standard mapping, or a result in an unexpected form.

The audited system responded by **inventing a plausible value**: it produced a `*1/*2` diplotype for
a gene it did not recognise. A fabricated genetic result is indistinguishable from a real one to a
reader, and it flowed into assessment as though it were measured fact. Principle V names this the
"confident value with no basis" failure.

Inventing values is prohibited outright. What remained open was what to do instead: reject the
unrecognised data at the door, or admit it while marking it unknown.

## Decision

**Unmapped genes are imported and recorded as explicit unknowns.** The reason is recorded and the
original unrecognised text is preserved for inspection. Nothing is assigned, inferred, or
approximated.

A gene recorded as unknown MUST NOT contribute to any severity, verdict, or alternative, and any
assessment that depends on one halts.

Drug names are treated differently and more strictly: a drug name that cannot be resolved in the
local vocabulary is refused outright and reported as unresolved. A near match is never selected.

## Consequences

**Accepted:**

- No data is silently discarded. A clinician can see that the record contained something the system
  did not understand, and what it was. Rejection at the door destroys that signal — the gene simply
  would not appear, which is the same absence that let the audited system proceed.
- Unknown is already a first-class value under Principle II, with an entry required for every
  in-scope gene. Importing unmapped genes as unknown reuses that mechanism rather than adding a
  second, quieter path for data that does not fit.
- The preserved original text makes coverage gaps diagnosable. A gene appearing repeatedly as unknown
  is evidence for extending the mapping, and that evidence only exists if the value was kept.
- Safety is identical to outright rejection: in both cases the value cannot reach a verdict, and any
  dependent assessment halts. The difference is only in how much is visible afterwards.

**Costs, accepted knowingly:**

- More unknown-handling paths to test than a flat rejection rule. Every surface that displays a
  profile must render an unknown-with-original-text case.
- The halt rate rises. This is expected and is recorded in SC-015: a sharp rise on introducing
  explicit unknowns is previously hidden gaps becoming visible, and MUST NOT be reported as a
  regression.
- Preserved original text is a data-handling surface. It stays inside the synthetic-data boundary and
  is subject to the same rule keeping patient identifiers out of logs.

## Alternatives considered

**Reject anything unmapped; import only recognised genes.** Equally safe against fabrication and
simpler to verify. Rejected because it discards diagnostic signal: the unmapped gene vanishes rather
than being visible as a gap, which resembles too closely the absence that caused the original defect.
Safety was not the deciding factor — both options are safe — visibility was.

**Stop accepting external records entirely; structured input only.** Eliminates the failure class by
removing the feature. Rejected as disproportionate. External record import is a legitimate capability
and the failure was fabrication, not ingestion.

**Ask a model to interpret unrecognised gene names.** Not seriously considered. Principle IX
prohibits a model reconciling suspect input, and models elaborate planted errors in up to 83% of
tested cases — precisely the wrong tool for deciding what an unrecognised genetic result means.

## Revisit when

- Unknown-marked genes from external records become numerous enough that reviewing them is itself a
  burden, suggesting the mapping needs extending rather than the policy changing.
- The system moves beyond synthetic data, where retaining unrecognised source text carries different
  handling obligations.
