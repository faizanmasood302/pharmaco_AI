<!--
SYNC IMPACT REPORT
==================
Version change:      (none) → 1.0.0
Bump rationale:      Initial ratification. No prior constitution existed at
                     `.specify/memory/constitution.md`; this is the first adoption,
                     so semantic versioning starts at 1.0.0 rather than a bump.

Source of authority: `HARNESS (1).md` v1.0 (21 Aug 2026), Parts II, III, IV, VII, IX, X, XI.
                     Part II is declared binding by the source document; its ten
                     invariants become Principles I–X verbatim in intent.

Modified principles: (none — initial adoption)

Added sections:
  - Core Principles I–X (derived from HARNESS Part II invariants I1–I10)
  - Regulatory Posture and Scope Boundary (HARNESS Part III)
  - Architectural Constraints (HARNESS Part IV.8, IX.4, IX.6)
  - Measurement and Quality Gates (HARNESS Part VII, IX.5)
  - Delivery Order (HARNESS Part X)
  - Governance

Removed sections:    (none)

Templates requiring updates:
  ⚠ pending  .specify/templates/plan-template.md      — FILE DOES NOT EXIST
  ⚠ pending  .specify/templates/spec-template.md      — FILE DOES NOT EXIST
  ⚠ pending  .specify/templates/tasks-template.md     — FILE DOES NOT EXIST
  ⚠ pending  .specify/templates/commands/*.md         — DIRECTORY DOES NOT EXIST
  ✅ aligned  CLAUDE.md — already states the invariants and the known divergences;
              no edit required for v1.0.0.
  ⚠ pending  README.md — quotes concordance figures above the last measured values;
              correction is governed by Delivery Order step 14, not by this amendment.

Deferred TODOs:
  - TODO(CLINICAL_REVIEWER): Principle V and the severity policy table require a named
    pharmacist signatory. Unresolved — HARNESS Part XI.1. Blocks any non-provisional
    severity row.
  - TODO(ENGINE_B_REVIEWER): Engine B sign-off requires a computational biologist,
    a different signatory from the clinical reviewer. Unresolved — HARNESS Part XI.8.
-->

# GenomicLens Constitution

**Pharmacogenomic and n-of-1 therapeutic decision support — a safety-critical medical AI harness.**

This constitution is binding on all contributors, human and agent. It derives its authority from
`HARNESS (1).md` v1.0, whose Part II declares its invariants binding and enforced "by types or
tests, not convention." Where this document and `HARNESS (1).md` disagree, `HARNESS (1).md` governs
and this document MUST be amended to match.

## Governing Thesis

> In safety-critical medicine, an LLM is a **rendering and inquiry layer over a verified
> deterministic core**, never the source of a clinical judgment. Every guarantee the system makes
> MUST be enforced by a mechanism outside the model, because a probabilistic component cannot bound
> its own error.

Two corollaries follow, and every principle below is an application of one of them:

1. **Agents do inquiry. Engines do judgment.** The boundary is enforced by the import contract, not
   by reviewer vigilance.
2. **A guarantee that is not mechanically enforced is not a guarantee.** Every principle in this
   constitution names the mechanism that enforces it. A principle whose enforcement mechanism does
   not yet exist is recorded as non-compliant, never as satisfied.

## Core Principles

### I. The Engine Holds All Clinical Authority

No LLM output MUST EVER become a risk level, a drug choice, a severity, or a gate decision. Model
output is confined to narrative and inquiry. No module under `engines/` may import any LLM client,
provider SDK, or agent module, transitively or directly.

**Enforcement:** `tests/invariants/test_llm_authority.py` asserts that no LLM client is importable
from `engines/`; `import-linter` fails the build on any violating edge.

**Rationale:** HARNESS F12. The guardrail literature converges on the principle that a model MUST
NOT be responsible for enforcing its own constraints. LLM-as-judge inherits the failure modes of
what it judges and cannot establish a deterministic lower bound on safety. This principle is why the
v1 adjudicator is deleted rather than improved.

### II. Unknown Is a First-Class Value That Halts

An absent, ambiguous, or uncovered phenotype MUST be represented explicitly and MUST halt
processing. `PhenotypeCall` MUST be a discriminated union of `KnownPhenotype | UnknownPhenotype`
with a `Field(discriminator="kind")` tag and **no default branch**. Every in-scope gene MUST have an
entry in `GenomicProfile.calls`; a gene the assay did not cover is present as
`UnknownPhenotype(reason="assay_does_not_cover")`, **never absent**.

`Outcome` and `Severity` are disjoint types. `Severity` is an `IntEnum`; `Outcome` MUST NOT be
orderable, comparable, or arithmetically combinable with it. No `max()`, `sorted()`, or clamp may
accept both.

**Enforcement:** the sealed union at the type level; the `phenotype_calls` table `CHECK
((kind='known') = (term IS NOT NULL))` constraint at the storage level.

**Rationale:** Audit findings CLIN-04 and CLIN-05. The audited system stored phenotype as a `str`
regex-extracted from a serialized blob, defaulting to `"normal metabolizer"` on failure. That single
modelling error produced three of five criticals. Absence is what let it silently proceed.

### III. Every Recommended Drug Is Assessed For This Patient

An alternative MUST NOT be offered unless it has been re-assessed by the same engine against the
same patient's genotype and the same indication. `AlternativeSet` MUST be constructible only from
`Assessment` objects, making the defect unrepresentable rather than merely tested for.
`safe_alternatives()` MUST require an `indication`. `NoSafeAlternative` is a legitimate
first-class result and MUST NOT be replaced by a fallback suggestion.

The `considered` set — including rejects and the reason for each rejection — MUST always be returned
and always be persisted.

**Enforcement:** the `AlternativeSet` constructor signature; the `alternatives_considered` table,
which stores rejects.

**Rationale:** Audit finding CLIN-03. The audited system offered duloxetine as a codeine substitute
because it had no indication and never re-scored candidates against the patient.

### IV. The System Is Fully Functional With The LLM Disabled

The complete evaluation suite MUST pass with `LLM_ENABLED=false`. That variable — not a
differently-named substitute — is the ablation switch, and it MUST be honoured at call time, never
resolved at module import. No core path may route through a model provider. A deterministic
narrative template MUST exist for every LLM-authored surface.

**Enforcement:** the `llm-disabled` CI job runs the full suite with `LLM_ENABLED=false`.

**Rationale:** HARNESS F12 and IX.0 rule 3. If the deterministic baseline cannot stand alone, then
the model is load-bearing and Principle I is false in practice regardless of what the code claims.
This is also what makes the Part VII.5 ablation study possible: if the agent layer does not beat the
deterministic baseline, that MUST be reported honestly.

### V. Every Clinical Claim Carries Provenance

Every scientific value in either engine MUST originate from a `ToolResult` recording tool name,
tool version, container digest, input and output SHA-256, and parameters. The report renderer MUST
refuse to render an unprovenanced field.

Clinical meaning MUST NOT be derived from prose. Severity is looked up in a reviewed policy table
carrying `guideline`, `table`, `guideline_version`, `doi`, and a named `reviewed_by`. Policy import
MUST fail closed on any row missing provenance or a reviewer field. A `(gene, phenotype, drug)`
triple absent from the table yields `NO_GUIDANCE` — **never `low`**. Rows without a reviewer load as
`provisional`, and every assessment touching one is flagged provisional in output. Provisional rows
MAY ship; they MUST NOT be hidden.

For third-party corpora, store **character offsets, not quoted text**, resolving spans from the
licensed local snapshot at display time.

**Enforcement:** renderer refusal on unprovenanced fields; fail-closed policy loader;
`severity_policy_rows.provisional` as a generated column derived from reviewer absence.

**Rationale:** HARNESS F2. Criterion 4 of the FD&C non-device CDS test requires that a professional
can independently review the *basis* of a recommendation. Provenance is not gold-plating; it is the
regulatory boundary. Two audited criticals came from reading clinical meaning out of free text
(`"avoid" in evidence.lower()`, substring phenotype matching). Deriving severity from CPIC
recommendation prose would be that same error a third time.

TODO(CLINICAL_REVIEWER): no named pharmacist has signed the severity policy table. Until one does,
every row is provisional and the system MUST present it as such.

### VI. Over-Flagging Is A Tracked Failure, Not A Safe Default

False positive rate is a **co-primary** metric, not a secondary one. Alert burden — the percentage
of combinations flagged, weighted by interruptiveness — MUST be measured and CI-gated. A change that
raises either MUST justify itself in the same pull request.

Interruptiveness MUST be tiered by severity: only blockers interrupt; `high` is passive and
persistent; `moderate` and `low` are in-context and non-persistent; `NO_GUIDANCE` is on-demand only;
`HALTED` interrupts but MUST be framed as **missing data**, never as risk. A one-directional `max()`
severity clamp is prohibited.

**Enforcement:** the `concordance` and `alert-burden` CI jobs; committed versioned JSON scorecards
so the delta appears in every diff.

**Rationale:** HARNESS F3, F4, F5. Alerts fire on roughly 13% of orders with about 90% of
drug-drug-interaction alerts overridden; in one emergency-department study only 7.3% of medication
alerts were judged clinically appropriate. Over-flagging is the dominant deployed failure mode of
this entire product category. The audited 29% false-positive rate is not a blemish; it is the
characteristic disease.

### VII. Server State Is Never Read From The Client

Every endpoint MUST accept identifiers. No endpoint may accept a state object, a gate status, an
approval flag, or any other server-owned value from a request body.

Gate state MUST be an append-only fold over `gate_transitions`; there is no updatable status column.
Approval MUST bind to an `assessment_sha256` content hash of exactly what was reviewed; when the
assessment changes, the hash no longer matches and the approval auto-transitions to `SUPERSEDED`.
`POST /v1/reports` MUST accept `{evaluation_id}` only, load server-side, fold the transition
history, verify `APPROVED`, and re-verify the hash.

**Enforcement:** endpoint signatures; `openapi-typescript`-generated frontend types make a violation
a compile error; the forged-body case is a permanent regression test.

**Rationale:** Audit finding CLIN-01. The audited `POST /clinical-note` read gate status from the
request body, so a forged approval was accepted. The corrected contract makes the attack
unrepresentable: there is no field in which to supply one. Requiring the hash also gives optimistic
concurrency, so approving a stale assessment is rejected rather than silently accepted.

### VIII. Citations Are Verified Against The Pinned Corpus Before Display

Every citation identifier in an LLM-authored narrative MUST resolve in the pinned corpus snapshot
before the narrative reaches a human. Retrieval MUST read a pinned immutable snapshot, never a live
API. `ai/gate.py` MUST reject any narrative containing an unresolvable citation.

The grounding gate MUST additionally verify: declared finding IDs exist in the assessment; declared
entities are a subset of the assessed drug plus validated alternatives; an **undeclared-entity scan**
matches the narrative text against the full local RxNorm lexicon and rejects any hit outside the
allowed set; no risk-bearing assertion contradicts the assessment's severity or outcome; a `HALTED`
or `NO_GUIDANCE` outcome yields no reassurance; and every blocker-severity finding appears in the
text.

**Failure policy:** reject → regenerate once with the violation fed back → reject again → fall back
to the deterministic template. Every rejection MUST be logged with the offending text.

The gate MUST be plain Python. It MUST NEVER be a model.

**Enforcement:** `ai/gate.py`; the `narratives` table records `gate_verdict` and
`rejection_reasons` per attempt.

**Rationale:** HARNESS F10 and F11. Physician-validated benchmarking found the best model still
hallucinating at 29.1%; fabricated guideline references are indistinguishable from real ones to a
rushed reader. Prompt-based mitigation moves clinical-summary hallucination from ~64% to ~43% — real
and insufficient — whereas a grounded pipeline measured 1.47%. The omission check exists because
grounding shifts the characteristic failure from inventing to leaving out, measured at 3.45%. The
rejection log is a measured hallucination rate for this system, a research artifact almost nobody
publishes.

### IX. Input Contradictions Halt And Are Never Reconciled By A Model

Every input MUST pass schema validation before reaching any agent. Two sources disagreeing on a
genotype MUST produce `HALTED`, surfaced to the human, naming both sources. It MUST NOT be silently
resolved, and it MUST NOT be handed to a model to adjudicate. Provenance MUST be recorded per input
field: which file, which assay, which timestamp. PHI heuristics fail closed; synthetic and public
data only.

An unmapped or unrecognised input MUST fail closed. Inventing a value — such as a `*1/*2` diplotype
for an unrecognised FHIR gene — is prohibited in any form.

**Enforcement:** `ProfileValidator` raises on conflicting genotype sources.

**Rationale:** HARNESS F9. Tested against 300 physician-designed vignettes each containing one
fabricated element, leading models repeated or elaborated the planted error in up to 83% of cases; a
mitigation prompt roughly halved that without eliminating it. Garbage in produces confident, fluent,
elaborated garbage out. Input validation is therefore a safety layer, not a hygiene chore.

### X. The Review Gate Is Not A Safety Control

The human approval gate is a workflow and accountability mechanism. Risk documentation, design
documents, code comments, marketing material, and regulatory correspondence MUST NOT cite human
review as mitigation for engine error.

The review interface MUST be **basis-first, verdict-second**: the reviewer sees genotype, guideline
text, and citation *before* the severity label. The `considered` set MUST always be shown.
Provisional and low-confidence findings MUST be visually distinct from reviewed ones. Override rate
MUST be monitored with alarms at **both** ends — above ~90% indicates alert fatigue, below ~5%
indicates automation bias. Neither is health.

**Enforcement:** review of risk documentation for prohibited mitigation claims; override-rate
monitoring with two-sided alarms.

**Rationale:** HARNESS F6, F7, F8 — the single most important design consequence in the source
document. When a system incorrectly flagged a medication as inappropriate, physician prescribing
errors rose by 56.9%; the human did not absorb the error, the erroneous assistance induced mistakes
the clinician would not otherwise have made. The 2026 Lancet analysis characterises human-in-the-loop
oversight as reassurance rather than protection. A gate that cannot be shown to catch engine error
MUST NOT be counted as though it does.

## Regulatory Posture and Scope Boundary

**Declared position: research and education only. Not a medical device. Does not provide medical
advice.** This MUST be rendered in the README, the API root, every UI surface, and every generated
document footer. Generated clinical notes MUST additionally carry a `SIMULATED` watermark and a
synthetic patient identifier. This is an architectural constraint, not a marketing footnote.

Even while positioned as research software, the system MUST be built to satisfy all four
§520(o)(1)(E) criteria, because retrofitting them is expensive:

| Criterion | Constraint |
|---|---|
| 1 — no image/IVD/signal analysis | Inputs are VCF, structured diplotypes, and FHIR text. Raw instrument signal and images MUST NEVER be ingested |
| 2 — displays medical information | Satisfied by construction |
| 3 — supports rather than directs | Output is an `Assessment` plus ranked considered options. No auto-prescribe path may exist in any code path |
| 4 — enables independent review | Satisfied by Principles V, III, VIII and the review interface. **This is the architecture** |

The line the product MUST NOT cross:

| Permitted | Prohibited |
|---|---|
| "This genotype implies reduced codeine activation per CPIC Table 2" | "Prescribe duloxetine" |
| Ranked options, each with its own assessment and basis | A single directive with the reasoning hidden |
| "No PGx-safe option in this formulary" | Silence, or a fallback suggestion that was never assessed |

## Architectural Constraints

**The import contract is the enforcement mechanism for Principle I** and MUST be checked by
`import-linter` in CI:

| Layer | May import | May NOT import |
|---|---|---|
| `domain` | nothing internal | everything |
| `engines` | `domain` | `ai`, `evidence`, `platform`, `api` |
| `evidence` | `domain` | `ai`, `engines`, `api` |
| `ai/agents`, `ai/gate` | `domain` | `engines`, `evidence`, `platform`, `api` |
| `ai/graph` | `domain`, `engines`, `evidence`, `ai/agents`, `ai/gate` | `platform.db`, `api` |
| `platform` | `domain` | `engines`, `ai` |
| `api` | all | — |

Two consequences are load-bearing and MUST NOT be relaxed: **`engines` cannot reach `ai`**, so a
future contributor cannot "just ask the model" inside the assessment path without the build
rejecting it; and **agents cannot reach the engines**, so `ai/agents/` receives already-computed
`Assessment` objects and has no way to invoke, influence, or re-run a judgment.

**Agent roles are bounded.** Intake MUST NOT emit a code unresolved in RxNorm. Evidence MUST NOT
produce a severity, verdict, or drug choice. Explain MUST NOT name a drug absent from the assessment
or state a risk absent from a finding. Q&A MUST answer "not covered" rather than answer beyond the
retrieved and assessed set. Coverage MUST NOT downgrade a gap into a reassurance. All agent calls
use Pydantic response schemas; free text is confined to fields explicitly typed as narrative.

**Deleted by constitutional mandate, and MUST NOT be reintroduced:** the LLM adjudicator (Principle
I), RxRisk as an agent (the engine does it deterministically), CostNavigator (unrelated to safety
and prone to fabrication), and **MisuseMonitor** — unvalidated LLM scoring of patient opioid-misuse
risk has no guideline backing, carries serious disparate-impact exposure, and is a category of
judgment that MUST NOT be model-made.

**Contract propagation is one-directional.** Pydantic domain types generate the FastAPI OpenAPI
schema, which generates the frontend TypeScript types and Zod schemas. Generated artifacts MUST be
committed, and drift MUST be a failing build rather than a runtime surprise.

**Failures are typed and MUST NEVER degrade into reassurance.** Tool container failure raises
`EngineError` and returns 5xx — never a fallback verdict. A database write failure propagates
`Result[T, WriteError]` — never a success-shaped response. A corpus snapshot outage degrades the
narrative to template while the assessment proceeds. A provider outage degrades to template with
full functionality retained.

**Anything that affects output MUST be pinned and recorded in `RunManifest`:** the `uv.lock` hash,
every tool image digest and version, corpus snapshot IDs per corpus, severity policy table version,
embedding model name and version, LLM model identifier, temperature and seed, golden-set version,
and application `spec_version`. If it affects output and is not on that list, it is a reproducibility
bug.

**Determinism applies to the engine path only.** Byte-identical output for identical input and seed
is gated for `engines/`. It MUST NOT be claimed for LLM output, since providers do not guarantee
reproducibility across serving conditions. Conflating the two would be a false reproducibility claim;
the LLM layer is covered instead by narrative rejection and omission rates.

## Measurement and Quality Gates

**Measurement MUST precede authority.** Promoting an unmeasured oracle to binding authority is the
same error class as defaulting an unknown phenotype to normal. The concordance harness MUST exist
before the engine is treated as authoritative.

The bar is near-total agreement, not "good accuracy." PGx guideline concordance is a **lookup**, not
a prediction: if CPIC says avoid codeine in a CYP2D6 ultra-rapid metabolizer, there is one correct
answer and it is knowable. Anything below near-total agreement on covered pairs is a bug, not model
error.

The golden set MUST be transcribed from CPIC's published tables with provenance per row and then
reviewed. It MUST NOT be generated from current system output — that measures self-consistency, not
correctness.

Gated metrics: concordance (exact `(outcome, severity)` match), false negative rate, false positive
rate, alert burden, halt rate, narrative rejection rate, narrative omission rate, citation
resolution failure rate, override rate (alarmed at both ends), per-gene and per-drug-class
breakdown, and determinism. Aggregate-only reporting is prohibited — a 46% aggregate hides which
module is broken.

A **sharp jump in halt rate** when the typed phenotype model lands is the bug becoming visible. It
MUST be reported as such and MUST NOT be treated as a regression.

Required CI jobs: `lint`, `typecheck` (mypy strict on `domain/` and `engines/`), `test`,
`invariants` (one file per principle), `llm-disabled`, `concordance`, `alert-burden`, `determinism`,
`contracts`, `frontend`. A PharmCAT or policy-table version bump MUST be accompanied by
re-measurement in the same pull request.

**No number may appear in an authoritative document unless it was measured.** Estimates MUST be
labelled as estimates. The audited system's documentation quoted 85% beside a measured 46%; this is
a constitutional violation, not a rounding difference.

## Delivery Order

Work is ranked by clinical risk removed per unit of effort. Reordering requires an amendment.

| # | Step | Closes |
|---|---|---|
| 1 | Golden set + concordance harness + CI gate; measure the current engine honestly | Measurement, Principle VI |
| 2 | Typed phenotype model; unknown halts | Principle II |
| 3 | Alternatives validated against the same patient | Principle III |
| 4 | Gate re-read server-side + state machine + content hash | Principles VII, X |
| 5 | PharmCAT adapter replaces hand-rolled rules and `guidelines.json` | Principle V |
| 6 | Severity policy table | Principle V |
| 7 | Delete adjudicator; engine authoritative | Principle I |
| 8 | Grounding gate | Principle VIII |
| 9 | Review interface redesign + override monitoring | Principle X |
| 10 | Authorization model + auth hardening | Regulatory posture |
| 11 | Data layer honesty + connection pool | Architectural constraints |
| 12 | Alert tiering | Principle VI |
| 13 | Delete therapy slice, MisuseMonitor, CostNavigator | Architectural constraints |
| 14 | Re-measure and correct all documentation | Measurement |
| 15 | *(later)* Engine B minimum slice | — |

**Steps 1–4 remove most of the clinical risk. If nothing else ships, ship those.**

Steps 1 and 2 have an unnumbered prerequisite: the ablation switch of Principle IV must actually
work, and the engine must make no network calls, or step 1 measures a non-deterministic,
covertly-LLM-assisted engine and reports the result as fact.

## Governance

**Supremacy.** This constitution supersedes all other development practices, including `AGENTS.md`,
`ARCHITECTURE-V2.md`, and any agent instruction file. Where it conflicts with `HARNESS (1).md`, the
source document governs and this constitution MUST be amended within the same pull request.

**Amendment procedure.** An amendment requires: (a) a pull request modifying this file; (b) a Sync
Impact Report prepended as an HTML comment recording the version change and affected artifacts;
(c) propagation to every dependent template and guidance document in the same pull request; and (d)
for any change to a Core Principle or a quality gate, an accompanying ADR under `docs/adr/`
recording what was decided and why. Principles MUST NOT be weakened to accommodate a deadline; the
correct response to a principle that blocks delivery is to raise the conflict, not to route around
it.

**Versioning policy.** Semantic versioning applies to governance semantics, not to prose:

- **MAJOR** — a principle is removed or redefined in a backward-incompatible way, or the layer
  contract, regulatory posture, or delivery order changes materially.
- **MINOR** — a principle or section is added, or existing guidance is materially expanded.
- **PATCH** — clarification, wording, typo, or other non-semantic refinement.

**Open decisions MUST be recorded, never silently picked.** The following remain unresolved and are
recorded under `docs/adr/` as they are settled: the named clinical reviewer; the criterion 1 IVD
boundary; PharmCAT licence terms and gene coverage; source precedence among CPIC, DPWG and FDA when
they disagree; indication vocabulary; severity scale; FHIR gene scope; Engine B timing and reviewer;
pgvector availability on the chosen managed Postgres; structured-output support for the specific
model behind the provider abstraction; and host capability for a second service. Choosing one of
these implicitly, in code, is a governance violation.

**Compliance review.** Every pull request MUST be checkable against the principles it touches.
Reviewers MUST verify that a claimed guarantee names its enforcement mechanism and that the
mechanism exists. Agent contributors MUST refuse to implement a change that violates a principle and
MUST raise the conflict instead of proceeding.

**Known non-compliance at ratification.** The current tree violates Principles I, IV, V, VI, VII and
the determinism constraint; the divergences are enumerated in `CLAUDE.md` and remediated in the
order given above. Ratification records the standard, not conformance to it. Existing violating code
MUST NOT be cited as precedent.

**Version**: 1.0.0 | **Ratified**: 2026-08-21 | **Last Amended**: 2026-08-21
