# ADR-0006: Retain the four-level severity scale

**Status**: Accepted
**Date**: 2026-08-23
**Decider**: M. Faizan (project owner)
**Closes**: `HARNESS.md` Part XI open decision 6 — "Severity scale. Keep four levels, or adopt
CPIC's own strength vocabulary directly? Fewer translation layers means fewer places to be wrong."
**Constitution reference**: Principle V (severity comes from a reviewed policy table, never derived
from prose); Principle VI (interruptiveness tiered by severity); Governance — open decisions
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-015, FR-015a, FR-052; Assumptions

## Context

`Severity` is an `IntEnum` with four members: `low`, `moderate`, `high`, `critical`. Three artifacts
already assume that shape:

- The **golden set** records `expected_severity` per case against those four values.
- The **spec** ties interruptiveness to them directly (FR-052, and the tiering table in
  `HARNESS.md` V.7): only `critical`/blocker interrupts, `high` is passive and persistent,
  `moderate` and `low` are in-context and non-persistent.
- The **severity policy table** carries `cpic_strength` and `severity` as separate columns, which is
  the translation layer the open decision asks about.

The alternative is to drop the four-level scale and use CPIC's own recommendation-strength
vocabulary (Strong / Moderate / Optional / No recommendation) as the severity directly, removing one
translation.

## Decision

**Four levels are retained: `low`, `moderate`, `high`, `critical`.**

The `cpic_strength` column stays alongside `severity`, and the mapping between them stays where
`HARNESS.md` V.4 puts it — in reviewable policy data with a named reviewer, not in code.

## Rationale

The golden set, the spec and the policy table all assume four levels. Changing the scale rewrites
all three, and there is no measured reason to change it now. Deferring a change that has no evidence
behind it is cheaper than making one and discovering it was unnecessary.

There is also a substantive reason the translation layer is not obviously waste, which is worth
recording so that a future reader does not remove it as redundant. CPIC strength answers "how good
is the evidence"; severity answers "what should this system do about it". `HARNESS.md` V.4 states
directly that the mapping from "Strong recommendation to avoid" to "block this prescription" is a
**product policy decision, not a fact**. Collapsing the two columns would move that decision out of
reviewable data and into the definition of the enum, where no pharmacist signs it. That is the same
class of error as deriving severity from guideline prose — the mechanism behind two of the audited
criticals.

The counter-argument in the open decision — fewer translation layers means fewer places to be wrong
— is real, and it is why this is recorded as revisitable rather than settled forever. It is
outweighed for now because the translation is *data*, and data with a reviewer is the project's
preferred place for a judgment call.

## Consequences

- No change to any existing artifact. This ADR records the status quo as chosen rather than
  defaulted, which is what the constitution requires of an open decision.
- The spec's Assumptions section — "Severity retains its current four-level scale until an
  architecture decision record says otherwise. This is recorded as an open decision rather than a
  settled default" — is now discharged. It should be updated to cite this ADR.
- Phase 5's policy table shape is unblocked. `severity` and `cpic_strength` are separate columns.
- The four levels are load-bearing for alert tiering, so a later change to the scale is also a change
  to the interruptiveness policy and to the alert-burden baseline. Any future revisit must re-measure
  alert burden in the same change.

## Revisit when

Measurement shows the CPIC-to-severity mapping loses information — for example, if two rows with
different `cpic_strength` values that map to the same `severity` turn out to warrant different
handling, or if the concordance harness shows disagreements clustering at a particular mapping
boundary. That is an empirical trigger, checkable from the per-gene and per-drug-class breakdown,
rather than a matter of preference.
