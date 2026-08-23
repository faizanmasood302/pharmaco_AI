# ADR-0002: CPIC alone determines severity

**Status**: Accepted
**Date**: 2026-08-21
**Decider**: M. Faizan (project owner)
**Constitution reference**: Governance — open decisions; Principles V and VI; Measurement
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-015a, User Story 6, SC-001

## Context

Three bodies publish pharmacogenomic prescribing guidance — CPIC, the Dutch Pharmacogenetics Working
Group (DPWG), and the FDA through drug labelling. They sometimes disagree for the same gene, phenotype
and drug: one may advise a dose reduction where another advises avoidance, and coverage differs.

A reference implementation can emit all three. Something must decide which governs. The constitution
forbids that precedence emerging implicitly from evaluation order and requires it recorded as a
decision.

## Decision

**CPIC is the sole source that determines severity.**

Other published sources may be displayed as clearly labelled context alongside a finding, but MUST
NOT set, raise, or lower a severity. A combination CPIC does not cover returns **no guidance**, even
where another source has published advice — and that other source's advice is shown as context that
explicitly did not set a severity.

## Consequences

**Accepted:**

- The headline agreement figure has exactly one meaning. Success criterion SC-001 targets ≥99%
  agreement measured against a case set transcribed from CPIC tables. If DPWG or FDA could also set
  severity, "agreement" would silently become a weighted blend across three sources with different
  coverage, and the number would stop being interpretable. The project is being rebuilt specifically
  to obtain trustworthy numbers; this preserves that.
- It matches what the constitution already declares — CPIC as the single declared source of truth,
  versioned, with agreement measured against CPIC specifically.
- One source means one version to pin, one set of tables to transcribe, and one provenance chain per
  claim. Three sources would multiply the provenance surface before any of it is measured.
- Precedence lives in reviewable policy data, not in code ordering, so it is inspectable and
  changeable without touching the assessment path.

**Costs, accepted knowingly:**

- Real coverage loss. Gene-drug pairs where only DPWG has published guidance return "no guidance"
  rather than an actionable finding. The advice is still visible to the clinician as context; it just
  carries no severity and triggers no alert.
- The "no guidance" rate will be higher than it would be under a multi-source rule. This is the
  honest figure and is tracked as such.
- If the system later ingests European records where DPWG is the operative standard, this decision
  becomes a limitation rather than a simplification.

## Alternatives considered

**Fixed precedence: CPIC → DPWG → FDA, with disagreements disclosed.** Genuinely attractive, and the
most likely successor to this decision. Rejected for now on sequencing grounds, not merit: it
requires agreement to be measured per source rather than in aggregate, which means three case sets
and three scorecards before the first number exists. Measurement comes first (Delivery Order step 1);
broadening the source set is a change to make against a working, measured baseline rather than
alongside its construction.

**Most conservative severity wins.** Rejected on safety grounds, which is the counterintuitive part
and worth stating plainly. Taking the strictest available answer feels cautious but raises the
false-positive rate, and over-flagging is the dominant deployed failure mode of this product
category: roughly 90% of interaction alerts are overridden, and in one emergency-department study
only 7.3% of medication alerts were judged clinically appropriate. Success criterion SC-002 exists to
cut the measured 29% false-positive rate to 5% or below. A max-severity rule works directly against
it. The constitution names one-directional severity clamping as a defect, not a default.

## Revisit when

- The concordance harness is in place, green, and has produced a stable CPIC baseline across at
  least one full release cycle.
- The "no guidance" rate attributable specifically to CPIC non-coverage is measured and material.
- The system's audience extends to jurisdictions where DPWG is the operative standard.

The likely successor is the fixed-precedence rule above, adopted with per-source measurement in the
same change.
