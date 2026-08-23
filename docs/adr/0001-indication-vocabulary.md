# ADR-0001: Indication vocabulary is a curated, version-controlled list

**Status**: Accepted
**Date**: 2026-08-21
**Decider**: M. Faizan (project owner)
**Constitution reference**: Governance — open decisions; Principle III
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-010, User Story 3

## Context

An alternative drug cannot be judged suitable without knowing what condition it is meant to treat.
The audited system had no indication at all, which is why it offered duloxetine — an antidepressant —
as a substitute for codeine, an analgesic. The substitute was pharmacogenomically clean and
therapeutically irrelevant.

Principle III therefore requires an indication on every alternatives request. The vocabulary for
expressing it was left open because three reasonable options exist with materially different scope.

## Decision

The indication is drawn from a **curated, version-controlled list of conditions** covering the
supported formulary. A value outside the list is refused rather than interpreted or approximated.

The list is treated as reviewable data on the same footing as the severity policy table: it is
versioned, it is diffable, and adding an entry is a reviewed change rather than a code edit.

## Consequences

**Accepted:**

- Scope matches reality. The formulary is roughly twenty drugs across opioids, SSRIs, statins,
  antiplatelets and analgesics; a hand-curated condition list at that scale is complete and auditable
  in a way a standards vocabulary subset would not be.
- No external vocabulary dependency, no licence question, and no large snapshot to pin — which
  matters because the assessment path may not reach the network.
- Every value in the list can be mapped deliberately to the formulary entries that treat it. Coverage
  gaps are visible as missing rows rather than hidden behind a code that resolves to nothing.

**Costs, accepted knowingly:**

- The list must be extended by hand as the formulary grows. This is intended: an indication that
  nothing in the formulary treats is a gap to notice, not a value to accept.
- Records arriving with ICD-10 or SNOMED codes will need a mapping layer if external ingestion of
  indications is added later. That mapping does not exist and is out of scope.
- The list is not interoperable with other systems. Acceptable while the system remains research and
  education software on synthetic data.

## Alternatives considered

**ICD-10 codes.** Familiar to clinicians, already present in records, no curation burden. Rejected
for now: ICD-10 is a billing and epidemiology classification, not a therapeutic one. Many codes map
to no formulary entry, and the granularity mismatch would push interpretation logic into code —
exactly where the constitution forbids clinical meaning from living.

**SNOMED CT concepts.** Clinically precise and FHIR-native, the correct long-term answer if the
system ever ingests real records. Rejected for now: licence terms, a large snapshot to pin offline,
and substantially more work than the current formulary justifies. This is a scale problem the project
does not yet have.

**Free text.** Not seriously considered. It would require a model to interpret the indication, which
Principle I prohibits in the assessment path.

## Revisit when

- The formulary exceeds roughly fifty drugs, or spans specialties where a hand-curated list stops
  being reviewable.
- Indications begin arriving from external records rather than being selected by the requester.
- Any non-research positioning is contemplated, where interoperability becomes a requirement rather
  than a convenience.

At that point ADR-0001 is superseded rather than amended, and the migration is a mapping from the
curated list to the chosen standard — which is tractable precisely because the list is explicit.
