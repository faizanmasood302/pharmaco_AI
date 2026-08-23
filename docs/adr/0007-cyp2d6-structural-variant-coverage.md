# ADR-0007: CYP2D6 structural variants — a second caller for the VCF path

**Status**: Accepted
**Date**: 2026-08-23
**Decider**: M. Faizan (project owner)
**Partially closes**: `HARNESS.md` Part XI open decision 3 — "PharmCAT licence and gene coverage."
The **coverage** half is closed here. The **licence** half remains open and still blocks Phase 5.
**Constitution reference**: Principle II (unknown is first-class and halts); Principle V (uncovered
means `NO_GUIDANCE`, never a hand-rolled fallback); Governance — open decisions
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-005, FR-007, User Story 2

## Context

PharmCAT does not call copy-number or complex structural variants. The CYP2D6 ultrarapid metabolizer
phenotype is defined by duplication or multiplication of normal-function alleles — `*1/*2x2` and
similar — and PharmCAT's own documentation states that UM "cannot be called using only SNPs and
INDELs in a VCF file", and that it does not recommend calling CYP2D6 from VCF at all because of the
influence of structural and copy-number variation.

This matters more here than it would elsewhere. CYP2D6 ultrarapid plus codeine is the flagship case:
it is the audited critical failure, the constitution's worked example in Principle II, and the case
that the whole "unknown must not become normal" argument is built on. Under the project's own rule
that uncovered means `NO_GUIDANCE`, the case that motivates the system would return no guidance.

**One fact narrows the problem, and it was verified rather than assumed.** PharmCAT accepts CYP2D6
diplotypes as **outside calls** (`-po`), and the workflow its documentation recommends is exactly
that: a specialised caller determines the CYP2D6 diplotype, PharmCAT's Phenotyper translates it and
the Reporter produces recommendations. `HARNESS.md` V.3 already names this as the project's path —
"Outside-call files accept diplotypes determined elsewhere — exactly your fixture and FHIR path."

So the gap is not "PharmCAT cannot reach CYP2D6 UM". The gap is **VCF-derived** CYP2D6: a diplotype
supplied to us as structured data flows through; a diplotype we would have to infer from a VCF does
not.

## Decision

**Option (a): a second caller for CYP2D6, behind the same `ToolAdapter` interface — scoped to the
VCF ingestion path only.**

| Input path | `source_kind` | CYP2D6 handling |
|---|---|---|
| Structured diplotypes (fixtures, FHIR) | `outside_calls`, `fhir_bundle` | Passed to PharmCAT as an outside call. No second caller involved. UM is reachable today |
| VCF | `vcf` | Requires the second caller. Until it lands, CYP2D6 from a VCF is `UnknownPhenotype(reason="assay_does_not_cover")` and any codeine-class assessment depending on it **halts** |

**Caller: PyPGx**, with StellarPGx as the named fallback. PyPGx runs from VCF plus read depth and
carries its own CYP2D6 structural-variant model, which fits a project with no WGS/BAM pipeline.
PharmCAT's documentation gives a worked outside-call example for StellarPGx specifically, so if the
PyPGx output mapping proves awkward, StellarPGx is the documented path. The choice is behind the
adapter, which is the entire reason the adapter exists.

Option (b) was rejected: it rests on a premise that holds only for VCF input. Marking CYP2D6
ultrarapid out of scope, and golden case **P-2D6-005** expected-`NO_GUIDANCE`, would encode a
limitation the system does not actually have on its primary input path — and would publish that
limitation to users as though it were general. Overstating a gap is a smaller error than hiding one,
but it is still a false statement about the system.

### Golden set consequence

`P-2D6-005` stays as it is: an outside-call fixture with a duplication diplotype, expected
`ACTIONABLE` / `critical`. A **companion case** is added — same patient, same drug, VCF-sourced —
expected `HALTED` with reason `assay_does_not_cover` until the second caller lands, and expected
`ACTIONABLE` / `critical` after. That companion case is how the gap stays visible in the scorecard
instead of living in a document, and how closing it becomes a measurable event rather than a claim.

### Verification owed at Phase 5

PharmCAT's documentation confirms it accepts CYP2D6 outside calls and translates them to phenotypes,
but does not explicitly state that the Phenotyper assigns UM from a supplied duplication diplotype
such as `*1/*2x2`. That is the behaviour this decision depends on, so it is an **acceptance check at
the start of Phase 5**, not an assumption to build on: feed `*1/*2x2` through the outside-call path
and confirm the Phenotyper returns ultrarapid. If it does not, this ADR is wrong about the scoping
and the second caller is needed on every path, not just VCF.

## Consequences

- Phase 5 gains a second adapter, restricted to one gene. It is not a general second engine, and it
  produces a diplotype for PharmCAT to phenotype rather than a phenotype of its own — the
  authority stays in one place.
- Both callers record `tool_version` and `container_digest` in `ToolResult` like any other tool, so
  a CYP2D6 call made by PyPGx is distinguishable in the provenance chain from one supplied as an
  outside call. A clinician reviewing the basis can see which it was.
- The `vcf` branch of `POST /v1/profiles` halts on CYP2D6 until the caller lands. That is the correct
  behaviour under Principle II and it will show as a halt-rate rise, which is the bug becoming
  visible rather than a regression.
- Two licences now need verifying rather than one: PharmCAT's, and PyPGx's. The licence half of open
  decision 3 stays open and still blocks Phase 5.
- Any gene beyond CYP2D6 affected by structural variation is out of scope of this decision and
  returns `NO_GUIDANCE` or halts under the ordinary rule. This ADR does not authorise a general
  pattern of adding callers to fill coverage gaps.

## Revisit when

- The Phase 5 acceptance check fails — the outside-call path does not yield UM — in which case the
  scoping in this decision is wrong and the second caller is needed everywhere.
- PharmCAT gains structural-variant calling, which would make the second caller removable.
- VCF ingestion turns out not to be a real input path for this system, in which case the second
  caller can be dropped entirely and the VCF branch removed rather than supported.
