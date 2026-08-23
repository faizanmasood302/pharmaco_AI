# Feature Specification: Constitution-Conformant Pharmacogenomic Safety Harness

**Feature Branch**: `001-pgx-safety-harness`
**Created**: 2026-08-21
**Status**: Ready for planning
**Input**: User description: "based on current constitution create a comprehensive specification"

## Overview

The system evaluates a proposed drug against a patient's pharmacogenomic profile and returns a
guideline-grounded assessment that a clinician can independently verify. This specification defines
that behaviour as governed by the project constitution v1.0.0, whose ten principles are binding.

The constitution ratified a standard the current system does not meet. This specification describes
a **replacement**, not a remediation: the existing implementation is treated as untrustworthy and is
being rebuilt against this specification rather than patched toward it. Existing behaviour is
evidence of what went wrong, never a precedent for what to keep.

The work is to make unknown data halt instead of reassure, make every recommendation verifiable,
make measurement honest, and make the model incapable of authoring a clinical judgment. Scope is
Engine A (pharmacogenomics). Engine B is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Measure the engine honestly before trusting it (Priority: P1)

A maintainer needs to know how often the system agrees with published guidance before anyone relies
on it. They run a scored evaluation against a reviewed set of cases transcribed from guideline
tables and receive a breakdown by gene and drug class, not a single aggregate.

**Why this priority**: The constitution forbids promoting an unmeasured oracle to binding authority.
Every other story's correctness claim is unverifiable until this exists. The last measured figures —
46% agreement, 29% false positives — are hand-run and stale, while published material quotes higher
numbers.

Because the engine is being replaced rather than corrected, the case set and scoring are deliberately
independent of any particular engine: they are the durable asset, written against published guideline
tables, and they outlive the implementation under test. Running them once against the outgoing
implementation costs little and produces the "before" figure that makes the replacement's improvement
demonstrable rather than asserted.

**Independent Test**: Run the evaluation against the reviewed case set on a system with no other
changes. It produces a scorecard with per-gene and per-drug-class rows, and a repeat run on the same
inputs produces identical figures.

**Acceptance Scenarios**:

1. **Given** a reviewed case set with expected outcome and severity per row, **When** the evaluation
   runs, **Then** it reports agreement rate, false negative rate, false positive rate, alert burden,
   and halt rate, each broken down by gene and by drug class.
2. **Given** a scorecard from a previous run, **When** a change lowers agreement or raises either
   error rate, **Then** the change is blocked and the specific regressed rows are named.
3. **Given** the same inputs and the same seed, **When** the evaluation runs twice, **Then** the two
   scorecards are identical.
4. **Given** a case set row, **When** a reviewer inspects it, **Then** it names the guideline table
   the expectation was transcribed from, and no row was derived from the system's own output.
5. **Given** a change to a source of clinical values, **When** it is proposed, **Then** re-measured
   figures accompany it in the same change.
6. **Given** the outgoing implementation, **When** the baseline is measured,
   **Then** it is measured twice — once with the language model disabled and
   once enabled — and both figures are recorded.

---

### User Story 2 - Missing genetic data stops the assessment (Priority: P1)

A clinician requests an assessment for a patient whose panel did not cover a gene relevant to the
drug. The system stops, says which gene is missing and why, and frames this as absent data rather
than as an absence of risk.

**Why this priority**: The single defect that produced three of five audited critical failures. A
system that silently treats "not tested" as "normal" is actively misleading at the exact moment a
clinician most needs the truth.

**Independent Test**: Submit a patient whose profile omits a gene the drug depends on. The response
halts and names the gap. No severity, no reassuring phrasing, no default value anywhere in it.

**Acceptance Scenarios**:

1. **Given** a patient whose panel did not cover a relevant gene, **When** an assessment is
   requested, **Then** the result is a halt naming the gene and the reason, and no severity is
   assigned.
2. **Given** a patient whose result for a relevant gene is ambiguous, **When** an assessment is
   requested, **Then** the result is a halt naming the ambiguity.
3. **Given** any patient profile, **When** it is retrieved, **Then** every in-scope gene has an
   explicit entry, and a gene the assay did not cover is present and marked as uncovered rather than
   omitted.
4. **Given** a halted assessment, **When** it is displayed, **Then** it interrupts the clinician but
   is framed as missing data, and contains no statement that the drug is safe or standard.
5. **Given** a drug-and-genotype combination with no published guidance, **When** an assessment is
   requested, **Then** the result states that no guideline exists, and is never presented as a
   low-risk finding.
6. **Given** any assessment path, **When** a halt and a severity meet, **Then** no operation can
   convert the halt into a severity value.

---

### User Story 3 - Alternatives are checked against this patient (Priority: P1)

A clinician receives a flagged assessment and needs a different option. Every alternative presented
has been evaluated against this patient's own genetics and the same clinical indication, and the
options that were ruled out are shown alongside the reason.

**Why this priority**: The audited system offered a substitute drug that had never been checked
against the patient, for a condition it does not treat. An unchecked alternative is more dangerous
than no alternative, because it carries the system's apparent endorsement.

**Independent Test**: Request an assessment for a patient with multiple relevant variants. Every
returned alternative has its own assessment attached, and the rejected candidates appear with
reasons.

**Acceptance Scenarios**:

1. **Given** a flagged drug and an indication, **When** alternatives are produced, **Then** each
   presented alternative carries its own assessment against this patient's profile.
2. **Given** a set of candidates, **When** alternatives are produced, **Then** the candidates that
   were ruled out are returned with the reason for each.
3. **Given** a patient for whom no candidate is suitable, **When** alternatives are requested,
   **Then** the system states plainly that no suitable option exists in the formulary and returns
   what it considered, rather than offering an unassessed fallback.
4. **Given** a request without an indication, **When** alternatives are requested, **Then** the
   request is refused, because a substitute cannot be judged suitable without knowing what it treats.
5. **Given** the reproduced cases from the original audit, **When** they are run, **Then** each
   produces the corrected result and remains a permanent regression case.

---

### User Story 4 - An approval covers only what was actually reviewed (Priority: P1)

A pharmacist reviews an assessment and approves it. The approval is bound to the exact content
reviewed. If the underlying assessment later changes, the approval lapses automatically rather than
silently carrying over.

**Why this priority**: The audited system read approval status out of the incoming request, so an
approval could be forged outright, and re-approval was unlimited. A clinician must never be recorded
as having approved something they never saw.

**Independent Test**: Approve an assessment, then change the underlying data. The approval no longer
authorises downstream output, and the history shows why.

**Acceptance Scenarios**:

1. **Given** a request to produce a clinical document, **When** it is submitted, **Then** the system
   determines approval status from its own records and ignores any status supplied by the caller.
2. **Given** a forged request asserting approval, **When** it is submitted, **Then** it is refused.
3. **Given** an approved assessment, **When** the underlying assessment changes, **Then** the
   approval lapses and downstream output is refused until re-review.
4. **Given** an approval attempt against a stale version, **When** it is submitted, **Then** it is
   refused rather than silently accepted.
5. **Given** any evaluation, **When** its history is requested, **Then** every state change is
   present with actor, role, rationale, and timestamp, and no prior entry has been altered or
   removed.
6. **Given** a role without approval authority, **When** approval is attempted, **Then** it is
   refused.

---

### User Story 5 - The clinician reviews the basis, not just the verdict (Priority: P2)

A clinician opens a flagged assessment and sees the genotype, the guideline text, and the citation
before the severity label. What was ruled out is visible. Provisional findings look visibly different
from reviewed ones.

**Why this priority**: This is the regulatory boundary. Non-device status depends on a professional
being able to independently review the basis rather than rely primarily on the output. A verdict
shown without its basis fails that test by construction. It is P2 only because Stories 1–4 must
make the basis correct before presenting it prominently.

**Independent Test**: Open a flagged assessment as a reviewer. The evidence is reachable before the
label, the ruled-out options are listed, and provisional rows are distinguishable at a glance.

**Acceptance Scenarios**:

1. **Given** a flagged assessment, **When** a reviewer opens it, **Then** genotype, guideline text,
   and citation are presented before the severity label.
2. **Given** an assessment with alternatives, **When** a reviewer opens it, **Then** the ruled-out
   options and their reasons are shown, not only the recommended ones.
3. **Given** a finding drawn from an unreviewed policy row, **When** it is displayed, **Then** it is
   visually distinct from a reviewed finding and labelled provisional.
4. **Given** a population of reviews, **When** override rate rises above the fatigue threshold or
   falls below the automation-bias threshold, **Then** an alarm is raised at that end.
5. **Given** published risk or design documentation, **When** it is reviewed, **Then** it does not
   claim human review as mitigation for engine error.

---

### User Story 6 - Every clinical claim traces to a guideline (Priority: P2)

A clinician selects any claim in the output and reaches the guideline table it came from, including
version and identifier. Nothing displayed lacks a traceable source.

**Why this priority**: Provenance is what makes independent review possible, and clinical meaning
derived from prose was the mechanism behind two audited critical failures.

**Independent Test**: For every claim in a rendered assessment, follow it to a source row. Any claim
without one is not rendered at all.

**Acceptance Scenarios**:

1. **Given** an assessment, **When** it is rendered, **Then** every clinical claim resolves to a
   guideline table row identifying guideline, table, version, and identifier.
2. **Given** a claim with no source, **When** rendering is attempted, **Then** the renderer refuses
   rather than rendering it unattributed.
3. **Given** a policy source missing provenance or a named reviewer, **When** it is loaded, **Then**
   loading fails and the system does not start.
4. **Given** a combination absent from the policy source, **When** it is assessed, **Then** the
   result is "no guidance", never a low-severity finding.
5. **Given** any displayed value, **When** its origin is traced, **Then** it is never the product of
   matching words in free text.
6. **Given** a completed assessment, **When** its full contributing chain is requested, **Then** the
   system returns every input, tool result, and policy row that contributed to the verdict.

---

### User Story 7 - Generated prose cannot exceed what was assessed (Priority: P2)

Narrative accompanying an assessment is checked before a human sees it. It cannot name a drug that
was not assessed, cite a source that does not exist, contradict the verdict, offer reassurance on a
halt, or omit a blocking finding.

**Why this priority**: A fabricated guideline reference is indistinguishable from a real one to a
rushed reader. Prompt instructions alone reduce this failure without eliminating it, so the check has
to sit outside the model.

**Independent Test**: Present narratives containing each violation class. Every one is refused, and
the refusal is recorded.

**Acceptance Scenarios**:

1. **Given** narrative naming a drug outside the assessed set, **When** it is checked, **Then** it is
   refused — including when the drug is mentioned only in passing and not declared.
2. **Given** narrative citing an unresolvable source, **When** it is checked, **Then** it is refused.
3. **Given** narrative contradicting the assessment's verdict or severity, **When** it is checked,
   **Then** it is refused.
4. **Given** a halted or no-guidance assessment, **When** narrative offering reassurance is checked,
   **Then** it is refused.
5. **Given** an assessment with a blocking finding absent from the narrative, **When** it is checked,
   **Then** it is refused for omission.
6. **Given** two consecutive refusals, **When** narrative is still required, **Then** the system
   presents a deterministic written summary instead, and the assessment is unaffected.
7. **Given** any refusal, **When** it occurs, **Then** the offending text and reason are recorded so
   the refusal rate can be reported.

---

### User Story 8 - The system reports what it does not know (Priority: P3)

A clinician asks what the system could not determine for a patient: which genes were not typed, which
drug pairs have no published guidance, and which findings rest on unreviewed policy.

**Why this priority**: A system that states its gaps plainly is more clinically useful, and more
defensible, than one that fills them with confident defaults. It had no equivalent in the audited
system.

**Independent Test**: Request coverage for a patient with a partial panel. The response lists the
gaps without softening any of them into reassurance.

**Acceptance Scenarios**:

1. **Given** a patient profile, **When** coverage is requested, **Then** untyped and uncovered genes
   are listed with the reason for each.
2. **Given** a patient and a drug set, **When** coverage is requested, **Then** pairs with no
   published guidance are listed as such.
3. **Given** findings resting on unreviewed policy, **When** coverage is requested, **Then** they are
   listed as provisional.
4. **Given** any coverage response, **When** it is read, **Then** no gap is phrased as an assurance
   of safety.

---

### User Story 9 - The system works with the language model switched off (Priority: P3)

An operator disables the language model entirely. Assessment, alternatives, halting, provenance,
review, and approval all continue to work. Only the prose changes, degrading to deterministic
summaries.

**Why this priority**: If the deterministic path cannot stand alone, the model is load-bearing and
every claim about it being non-authoritative is false in practice. This is also what makes it
possible to report honestly whether the model layer improves on the baseline at all.

**Independent Test**: Disable the model and run the full evaluation. Every result matches the
enabled run except narrative phrasing.

**Acceptance Scenarios**:

1. **Given** the model is disabled, **When** the full evaluation runs, **Then** it passes completely.
2. **Given** the model is disabled, **When** an assessment is requested, **Then** verdict, severity,
   findings, and alternatives are identical to the enabled run.
3. **Given** the model is disabled, **When** narrative is required, **Then** a deterministic written
   summary is produced.
4. **Given** the model provider is unreachable, **When** an assessment is requested, **Then** the
   system degrades to deterministic summaries without failing the assessment.
5. **Given** the enabled and disabled runs, **When** they are compared, **Then** the comparison is
   published even when the model layer does not improve on the baseline.

---

### User Story 10 - Alerts are tiered so the important ones stay visible (Priority: P3)

A clinician working through a patient list is interrupted only by blocking findings. Lower-severity
findings appear in context without interrupting, and no-guidance results are available on request.

**Why this priority**: Roughly 90% of interaction alerts are overridden, and in one study only 7.3%
were judged clinically appropriate. Alert burden is the mechanism by which a technically correct
system becomes clinically useless.

**Independent Test**: Run a representative caseload and count interruptions. Only blocking findings
interrupt, and total burden is reported.

**Acceptance Scenarios**:

1. **Given** a blocking finding, **When** it is surfaced, **Then** it interrupts.
2. **Given** a high-severity finding, **When** it is surfaced, **Then** it is persistent and
   in-context but does not interrupt.
3. **Given** a moderate or low finding, **When** it is surfaced, **Then** it is in-context and
   non-persistent.
4. **Given** a no-guidance result, **When** it is surfaced, **Then** it is available on request only.
5. **Given** a change that raises the interruptive alert rate, **When** it is proposed, **Then** it is
   blocked unless accompanied by a recorded policy justification.
6. **Given** a patient with results already on file versus one without, **When** alerts are
   generated, **Then** the two situations are treated distinctly.

---

### Edge Cases

- Two sources disagree on the same gene for the same patient. The assessment halts, names both
  sources, and is never resolved automatically or by a model.
- A drug name cannot be resolved in the local reference vocabulary. The system reports it as
  unresolved rather than guessing, and does not consult an external service during assessment.
- A gene arrives from an external record with no recognised mapping. It is imported and recorded as
  an explicit unknown with its original text preserved, never assigned an invented value, and any
  assessment depending on it halts.
- The evidence corpus is unavailable. The assessment still completes; only the narrative degrades.
- A tool that produces clinical values fails. The request errors rather than returning any verdict.
- A storage write fails. The caller receives an error, never a success-shaped response.
- The same patient and drug is assessed twice with unchanged inputs. Results are identical.
- A policy version changes after an approval. Existing approvals lapse.
- An assessment is requested for a patient the requester has no relationship with. It is refused.
- A patient has variants in several genes affecting the same drug. All are reported; none is
  collapsed into a single worst-case label by an ordering operation.
- Guideline sources disagree for the same combination. CPIC governs the severity; the disagreement is
  disclosed as labelled context rather than hidden or averaged.
- A combination has advice from another source but none from CPIC. The result is "no guidance", and
  the other source's advice is shown as context that did not set a severity.

## Requirements *(mandatory)*

### Functional Requirements

**Clinical authority**

- **FR-001**: System MUST derive every risk level, severity, drug choice, and approval decision from
  deterministic logic. No language model output may become any of these.
- **FR-002**: System MUST prevent the assessment path from invoking, consulting, or being influenced
  by a language model, and MUST fail its build if such a dependency is introduced.
- **FR-003**: System MUST NOT include any component in which a model arbitrates between or overrides
  deterministic findings.

**Unknown and halting**

- **FR-004**: System MUST represent every in-scope gene explicitly for every patient, including genes
  the assay did not cover.
- **FR-005**: System MUST halt when any gene relevant to the requested drug is untyped, ambiguous, or
  uncovered, and MUST name the gene and the reason.
- **FR-006**: System MUST treat "no guidance" and "halted" as outcomes that cannot be ordered,
  compared, or combined with severity values.
- **FR-007**: System MUST return "no guidance" for any combination absent from the policy source, and
  MUST NOT substitute a low-severity result.
- **FR-008**: System MUST present halts as missing data and MUST NOT include any statement implying
  safety or standard dosing in a halted result.

**Alternatives**

- **FR-009**: System MUST evaluate every candidate alternative against the requesting patient's own
  profile before presenting it.
- **FR-010**: System MUST require a clinical indication for any alternatives request and MUST refuse
  the request without one. The indication MUST come from a curated, version-controlled list of
  conditions covering the supported formulary, and a value outside that list MUST be refused rather
  than interpreted (ADR-0001).
- **FR-011**: System MUST return the full considered set, including ruled-out candidates and the
  reason for each rejection.
- **FR-012**: System MUST report "no suitable option" as a valid result and MUST NOT substitute an
  unassessed suggestion.

**Provenance and policy**

- **FR-013**: System MUST attach to every scientific value a record of the tool, version, pinned
  image identity, input and output fingerprints, and parameters that produced it.
- **FR-014**: System MUST refuse to render any clinical claim lacking a traceable source.
- **FR-015**: System MUST source severity from a reviewed policy table carrying guideline, table,
  version, identifier, and reviewer, and MUST NOT derive severity by matching words in guideline
  prose.
- **FR-015a**: System MUST treat CPIC as the sole source that determines severity. Other published
  sources MAY be displayed as context, clearly labelled, but MUST NOT set, raise, or lower a
  severity. A combination CPIC does not cover MUST return "no guidance" even where another source
  has published advice (ADR-0002).
- **FR-016**: System MUST fail to start when any policy row lacks provenance or a reviewer field.
- **FR-017**: System MUST mark findings from unreviewed policy rows as provisional in every surface
  that displays them, and MUST derive provisional status from the absence of a reviewer rather than
  storing it independently.
- **FR-018**: System MUST make the complete chain of inputs, tool results, and policy rows behind any
  verdict retrievable.
- **FR-019**: System MUST store third-party guideline references as locations within a licensed local
  snapshot rather than as copied text.

**Server-owned state**

- **FR-020**: System MUST accept only identifiers on requests that act on stored state, and MUST
  reject any caller-supplied approval status, gate state, or assessment content.
- **FR-021**: System MUST record review state as an append-only history and derive current state from
  that history.
- **FR-022**: System MUST bind each approval to a fingerprint of the exact content reviewed, and MUST
  lapse the approval when that content changes.
- **FR-023**: System MUST reject an approval submitted against a version other than the current one.
- **FR-024**: System MUST restrict approval to the designated approving role, and MUST resolve access
  to any patient-scoped request against an explicit care relationship.

**Narrative control**

- **FR-025**: System MUST check every generated narrative before a human sees it, refusing any that
  names an unassessed entity, cites an unresolvable source, contradicts the verdict, reassures on a
  halt, or omits a blocking finding.
- **FR-026**: System MUST detect named entities the narrative did not declare, by matching the text
  against the complete local drug vocabulary.
- **FR-027**: System MUST retry once with the violation supplied, then fall back to a deterministic
  summary, and MUST NOT present unchecked narrative under any condition.
- **FR-028**: System MUST record every refusal with the offending text and reason, and MUST report
  the resulting refusal and omission rates.
- **FR-029**: System MUST implement the narrative check as deterministic logic and MUST NOT use a
  model to perform it.

**Input integrity**

- **FR-030**: System MUST validate every input against its schema before any agent processes it.
- **FR-031**: System MUST halt on contradictory sources for the same gene, naming both sources, and
  MUST NOT resolve the contradiction automatically or by model.
- **FR-032**: System MUST record per input field which source, assay, and timestamp it came from.
- **FR-033**: System MUST NOT assign, infer, or invent a value for any input it cannot map to a
  recognised term, under any circumstance.
- **FR-033a**: System MUST import a gene arriving from an external record even when it has no
  recognised mapping, recording it as an explicit unknown with the reason and the original
  unrecognised text preserved for inspection (ADR-0003).
- **FR-033b**: System MUST NOT allow a gene recorded as unknown to contribute to any severity,
  verdict, or alternative, and MUST halt any assessment that depends on one.
- **FR-033c**: System MUST refuse a drug name it cannot resolve in the local vocabulary, reporting it
  as unresolved rather than selecting a near match.
- **FR-034**: System MUST reject inputs that appear to contain real patient identifiers.

**Measurement**
User story
- **FR-035**: System MUST provide a reviewed evaluation case set transcribed from published guideline
  tables with a source recorded per case, and MUST NOT generate cases from its own output.
 **FR-035a**: Only a human may record a case as verified. An automated
  contributor MUST NOT create or modify a verification attestation under any
  circumstance, including to clear a failing gate.
- **FR-036**: System MUST report agreement rate, false negative rate, false positive rate, alert
  burden, halt rate, narrative refusal rate, narrative omission rate, source resolution failure rate,
  and override rate.
 - **FR-036a**: System MUST report agreement separately for two stages: assigning
  a phenotype from a genotype, and producing a recommendation from a phenotype
  and drug. A combined figure MUST NOT be reported without both component
  figures alongside it.
- **FR-037**: System MUST report every metric broken down by gene and by drug class in addition to any
  aggregate.
- **FR-038**: System MUST block a change that lowers agreement or raises either error rate, and MUST
  block a change raising interruptive alert rate without a recorded justification.
- **FR-039**: System MUST require re-measurement in the same change whenever a source of clinical
  values changes.
- **FR-040**: System MUST produce identical assessment output for identical inputs and seed, and MUST
  verify this automatically.
- **FR-041**: System MUST record, for every run, every pinned input that can affect output.
- **FR-042**: System MUST NOT publish an unmeasured figure as though it were measured, in any
  document it controls.

**Operating without the model**

- **FR-043**: System MUST pass its complete evaluation with the language model disabled by a single
  documented setting.
- **FR-044**: System MUST resolve that setting at the time of use, not at process start, so it is
  effective in every environment.
- **FR-045**: System MUST provide a deterministic written summary for every narrative surface.
- **FR-046**: System MUST degrade to deterministic summaries when the provider is unavailable, without
  failing the assessment.

**Determinism of the assessment path**

- **FR-047**: System MUST NOT make outbound network calls from the assessment path. Reference data
  MUST be local and versioned.
- **FR-048**: System MUST return an error when a tool producing clinical values fails, and MUST NOT
  return any verdict in that case.
- **FR-049**: System MUST surface storage failures to the caller and MUST NOT return a success-shaped
  response when a write failed.

**Presentation and posture**

- **FR-050**: System MUST present genotype, guideline text, and citation before the severity label in
  the review surface.
- **FR-051**: System MUST show the considered set wherever alternatives are shown.
- **FR-052**: System MUST tier interruptiveness by severity, interrupting only for blocking findings
  and for halts framed as missing data.
- **FR-053**: System MUST monitor override rate and alarm at both a high and a low threshold.
- **FR-054**: System MUST distinguish patients with results on file from those without when
  generating alerts.
- **FR-055**: System MUST display its research-and-education-only, not-a-medical-device statement on
  every user-facing surface, at the interface root, and in every generated document footer.
- **FR-056**: System MUST mark every generated clinical document as simulated and carrying a synthetic
  patient identifier.
- **FR-057**: System MUST NOT provide any path that issues a prescription or directs an action, and
  MUST present output as considered options with their basis.
- **FR-058**: System MUST NOT claim human review as mitigation for engine error in any documentation
  it controls.

**Records**

- **FR-059**: System MUST record every access to patient-scoped data with actor, action, resource, and
  time, in an append-only record.
- **FR-060**: System MUST keep patient identifiers out of application logs.

### Key Entities

- **Patient Genomic Profile** — the set of gene results for one patient, with an entry for every
  in-scope gene and a record of what the assay actually covered.
- **Phenotype Call** — one gene's result: either a known value with its vocabulary, diplotype, and
  source, or an explicit unknown with a reason. These two forms are distinct and a known value cannot
  exist without a term.
- **Assessment** — the immutable outcome for one patient-and-drug pair: outcome, severity where
  applicable, findings, and the policy and evidence versions in force. Identified by a fingerprint of
  its content.
- **Finding** — one gene-level contribution to an assessment, with its severity, recommended action,
  originating policy row, and provisional status.
- **Considered Set** — every alternative evaluated for a request, ranked where suitable and rejected
  with a reason where not.
- **Severity Policy Row** — the reviewed unit of clinical meaning: gene, phenotype, drug, guideline
  strength, severity, action, interruptiveness, provenance, and reviewer. Provisional when no
  reviewer is recorded.
- **Evaluation** — a reviewable record of an assessment, whose current state is the fold of its
  transition history.
- **Gate Transition** — one append-only state change, with actor, role, rationale, the content
  fingerprint reviewed, and time.
- **Narrative** — generated prose with the findings, sources, and entities it declares, its check
  verdict, refusal reasons, and attempt number.
- **Citation** — a location within a pinned corpus snapshot: corpus, snapshot, document, section, and
  offsets.
- **Tool Result** — the provenance record for any produced scientific value.
- **Evaluation Case** — one reviewed expectation: patient fixture, drug, expected outcome and
  severity, and the guideline table it was transcribed from.
- **Run Manifest** — every pinned input for one run, sufficient to reproduce it.
- **Care Relationship** — the explicit link authorising an actor to act on a patient's data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agreement with published guidance on covered combinations reaches at least 99%,
  measured against the reviewed case set, reported per gene and per drug class.
- **SC-002**: False positive rate on the reviewed case set falls to 5% or below, from a measured
  starting point of 29%.
- **SC-003**: No assessment in the reviewed case set presents an untyped, ambiguous, or uncovered gene
  as a normal result. Target: zero occurrences.
- **SC-004**: Every alternative shown to a clinician carries its own assessment for that patient.
  Target: 100%, with zero unassessed suggestions across the full case set.
- **SC-005**: Every clinical claim displayed resolves to a guideline source. Target: 100%, with the
  renderer refusing rather than displaying any exception.
- **SC-006**: The complete evaluation passes with the language model disabled, and verdicts, findings,
  and alternatives are identical to the enabled run for 100% of cases.
- **SC-007**: Identical inputs and seed produce identical assessment output on 100% of repeat runs.
- **SC-008**: No approval remains valid against changed content. Target: zero, verified by attempting
  downstream output after every form of change.
- **SC-009**: No request succeeds in supplying its own approval status, gate state, or assessment
  content. Target: zero accepted across all such endpoints.
- **SC-010**: Narrative refusal rate and omission rate are measured and published for every release,
  establishing a baseline where none exists today.
- **SC-011**: No generated narrative reaching a clinician names an unassessed drug, cites an
  unresolvable source, or contradicts its verdict. Target: zero across the full case set.
- **SC-012**: Interruptive alerts fire only for blocking findings and halts. Total alert burden is
  reported per release and does not rise without a recorded justification.
- **SC-013**: Override rate stays between the automation-bias and fatigue thresholds, with an alarm
  raised at either end within one reporting period of a breach.
- **SC-014**: A clinician can reach the guideline basis for any verdict without leaving the review
  surface, in a single step.
- **SC-015**: Halt rate is reported per release. A rise on introduction of explicit unknowns is
  recorded as previously hidden gaps becoming visible, not as a regression.
- **SC-016**: Every figure in project documentation is either measured and dated, or labelled an
  estimate. Target: zero unlabelled estimates.
- **SC-017**: No assessment makes an outbound network call. Target: zero, verified with external
  access blocked.
- **SC-018**: Every patient-scoped access resolves against an explicit care relationship, and every
  access is recorded. Target: 100%.

## Assumptions

- Scope is Engine A, pharmacogenomics. The mRNA design engine is explicitly excluded.
- The system remains research and education software on synthetic data. It is not a medical device
  and no clinical deployment is in scope, though it is built to satisfy the non-device criteria
  because retrofitting them later is expensive.
- CPIC is the single declared source of clinical truth, versioned, and agreement is measured against
  CPIC specifically (ADR-0002). Divergent commercial interpretations are out of scope.
- The existing implementation is being replaced, not incrementally corrected. Its measured behaviour
  serves as a baseline to improve on and as a catalogue of failures to regression-test; it is not a
  reference for correct behaviour, and its code is not precedent.
- Existing patient fixtures and drug coverage define the initial evaluation set. Coverage expands
  with the policy table, not ahead of it.
- Severity uses a four-level scale (low, moderate, high, critical), retained deliberately rather
  than by default (ADR-0006). The mapping from CPIC recommendation strength to severity stays in
  reviewable policy data with a named reviewer, because it is a product policy decision rather than
  a fact.
- Genes and drug pairs outside the policy table return "no guidance". No hand-written fallback fills
  the gap.
- Approval authority rests with a pharmacist role; clinician, researcher, and administrator roles do
  not hold it.
- Determinism is claimed for the assessment path only. Generated prose is not reproducible and is
  covered instead by refusal and omission rates.
- Thresholds for override-rate alarms follow the published fatigue and automation-bias figures until
  local data supports revising them.
- The named clinical reviewer required for non-provisional policy rows is not yet appointed. The
  system ships with provisional rows visibly marked rather than waiting or hiding them.

## Dependencies

- **A named clinical reviewer** must sign the severity policy table. Until then every row is
  provisional. This is a blocking dependency for any non-provisional clinical claim, not a
  nice-to-have.
- **A pinned local copy** of guideline tables, gene definitions, and the drug vocabulary, versioned
  and offline, since the assessment path may not reach the network.
- **A licensed local corpus snapshot** for evidence retrieval, stored so that referenced text is
  resolved at display time rather than copied.
- **Confirmation of licence terms and gene coverage** for any adopted reference implementation of
  guideline logic. Anything uncovered is "no guidance", never a hand-rolled substitute.
- **Architecture decision records** for the open decisions the constitution forbids picking silently.
  Three are now recorded as ADR-0001, ADR-0002 and ADR-0003; the remainder stay open and are listed
  in the constitution's governance section.
- Current documentation quoting unmeasured figures must be corrected once measurement exists.
  Sequenced deliberately after measurement, not before.

## Resolved Decisions

Three decisions materially affected scope and could not be defaulted. Each was decided by the project
owner on 2026-08-21 and recorded as an architecture decision, per the constitution's requirement that
open decisions be recorded rather than picked silently.

| ADR | Decision | Effect on this spec |
|---|---|---|
| [ADR-0001](../../docs/adr/0001-indication-vocabulary.md) | Indication comes from a curated, version-controlled list of conditions covering the supported formulary | FR-010; Story 3 |
| [ADR-0002](../../docs/adr/0002-guideline-source-precedence.md) | CPIC alone determines severity; other sources may be shown as labelled context only | FR-015a; Story 6; SC-001 |
| [ADR-0003](../../docs/adr/0003-external-record-import-scope.md) | Unmapped genes from external records are imported as explicit unknowns, never rejected silently and never assigned a value | FR-033a/b; Story 2; SC-015 |

Three further decisions were recorded on 2026-08-23:

| ADR | Decision | Effect on this spec |
|---|---|---|
| [ADR-0005](../../docs/adr/0005-agent-framework.md) | OpenAI Agents SDK for the agent layer, `as_tool()` only, `handoff()` prohibited, tracing disabled, schema parse-failure rate measured | FR-025, FR-029, FR-036; Story 7 |
| [ADR-0006](../../docs/adr/0006-severity-scale.md) | Four-level severity scale retained | FR-015, FR-052; Assumptions |
| [ADR-0007](../../docs/adr/0007-cyp2d6-structural-variant-coverage.md) | A second caller covers CYP2D6 structural variants on the VCF path only; the outside-call path is unaffected | FR-004, FR-005, FR-007; Story 2 |

Decisions still open, and deliberately not chosen here: criterion 1 IVD boundary, reference
implementation **licence** terms, Engine B timing and reviewer, pgvector availability on the chosen
managed Postgres, host capability for a second service, and the named clinical reviewer. They are
listed in the constitution's governance section and remain blocking where noted in Dependencies.
