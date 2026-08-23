# Phase 0 Research — 001 PGx Safety Harness

**Date**: 2026-08-23 | **Feeds**: [plan.md](./plan.md)

The stack was fixed in advance by `HARNESS.md` Part IX and by the project owner's plan input, so
this document does not re-derive settled choices. It records the two places where those two sources
disagree, the disposition of the eleven open decisions the constitution forbids picking silently,
and the small number of technical facts the plan depends on that had to be verified rather than
assumed.

## 1. Divergences between the owner's stack input and `HARNESS.md` IX.1

### D-1 · Agent orchestration: OpenAI Agents SDK, not LangGraph — **amended 2026-08-23**

- **Decision**: the agent layer is built on the OpenAI Agents SDK, restricted to `Agent.as_tool()`
  composition. `handoff()` is prohibited. No tool wraps an engine call. SDK tracing is disabled.
- **Rationale**: `as_tool()` gives the shape the constitution already requires — a called agent
  receives generated input, returns a typed result, and returns control to the caller, so it cannot
  take over the run. `handoff()` transfers control, which is the mechanism by which an agent would
  come to route a clinical judgment; prohibiting it keeps Principle I structural rather than
  behavioural. Typed `output_type` deletes `agents/base.py::parse_opinion`, which regexed a JSON
  object out of prose and returned `{}` on failure. The SDK's own tool loop removes the hand-rolled
  loop that appended one synthetic assistant message per tool call and thereby suppressed parallel
  tool calling.
- **Provider**: unchanged from ADR-0004 — Anthropic, `claude-opus-5`, reached through the SDK's
  LiteLLM extension (`openai-agents[litellm]`, `LitellmModel` / `LitellmProvider`), still behind the
  internal `LlmClient` protocol. Verified against the SDK reference: `LitellmModel` exists precisely
  to route Agents-SDK runs to Anthropic and other non-OpenAI providers.
- **Tracing**: the SDK traces to OpenAI by default. That would send clinical narrative and patient
  context to a third party and would duplicate, badly, the `RunManifest` and `narratives` tables
  that exist to keep the audit trail in our own Postgres. `set_tracing_disabled(True)` is a
  correctness requirement here, not a preference — the same reasoning that removed LangSmith in
  ADR-0004.
- **Alternatives considered**: LangGraph, as `HARNESS.md` IX.1 specifies — deferred, not rejected;
  its value is checkpointed typed state, and the pipeline is near-linear (validate → assess →
  retrieve → explain → gate). Plain async Python, as ADR-0004 chose — superseded, because it leaves
  the structured-output and tool-loop defects to be hand-rebuilt. LangChain — rejected permanently
  in ADR-0004 and not revisited.
- **Structured output is measured, not assumed**: the OpenAI-compatible layer does not guarantee
  schema conformance and ignores the `strict` parameter for function calling. Schema parse-failure
  rate is therefore a reported metric alongside narrative refusal and omission rates. If it proves
  material, the narrative agents move to the native provider SDK behind the same `LlmClient`
  protocol, with no change above that protocol.
- **Status**: recorded as ADR-0005 and **in force**. `HARNESS.md` IX.1 orchestration row, settings
  row, IX.6 pin list and the MANIFEST AI-layer table were amended on 2026-08-23 (v1.0 → v1.1);
  `ai/graph` was renamed `ai/orchestration` in IV.8, IV.11 and IX.7 and in the constitution's
  Architectural Constraints table (v1.0.0 → v1.0.1, PATCH — a rename, not a change to the contract).
  **P0-1 and P0-2 are discharged.**

### D-2 · LLM sampling settings are not settable

- **Finding**: `HARNESS.md` IX.1 specifies `temperature=0, seed where supported`, and IX.6 lists
  "LLM model identifier, temperature, seed" among the values pinned in `RunManifest`. The pinned
  model rejects `temperature` and `top_p` outright; there is no seed parameter.
- **Disposition**: recorded in ADR-0004; **amended 2026-08-23**. The IX.1 settings row now states
  that no sampling parameters are settable, IX.6 pins the model identifier alone, and the
  constitution's pin sentence follows.
- **What this does and does not change**: `RunManifest` continues to pin the model identifier and
  every engine-path input. It stops pinning two parameters that do not exist. Determinism was never
  claimed for the LLM layer — `HARNESS.md` IX.3 says so explicitly, and the constitution covers the
  model layer by narrative refusal and omission rates instead. The amendment removed a setting, not
  a guarantee, and the schema parse-failure metric added under D-1 covers the gap it leaves.

## 2. Disposition of the eleven open decisions

`HARNESS.md` Part XI. The constitution's governance section makes choosing one of these implicitly,
in code, a governance violation.

| # | Decision | Status | Effect on this plan |
|---|---|---|---|
| 1 | Named clinical reviewer for the severity table | **Open — external dependency** | Every policy row loads `provisional` and every touching assessment is flagged. Ships visibly provisional; does not block any phase |
| 2 | Criterion 1 IVD boundary (structured diplotypes vs instrument signal) | Open | No effect while the product is research-only. Inputs are restricted to VCF, structured diplotypes and FHIR text; raw instrument signal and images are never ingested |
| 3a | PharmCAT **licence terms** | **Open — blocks Phase 5** | Now covers PyPGx's licence too, following ADR-0007 |
| 3b | PharmCAT **gene coverage** | **Closed — ADR-0007** | PharmCAT does not call CNV or complex structural variants, so CYP2D6 ultrarapid is unreachable **from a VCF**. It *is* reachable through the outside-call path, which is this project's fixture and FHIR path. A second caller (PyPGx, StellarPGx as fallback) covers CYP2D6 on the VCF path only, behind the same `ToolAdapter` |
| 4 | Source precedence among CPIC, DPWG, FDA | **Resolved — ADR-0002** | CPIC alone determines severity; others display as labelled context. A combination CPIC does not cover returns `NO_GUIDANCE` even where another source has advice |
| 5 | Indication vocabulary | **Resolved — ADR-0001** | A curated, version-controlled condition list covering the supported formulary. A value outside it is refused, not interpreted |
| 6 | Severity scale: four levels, or CPIC's own strength vocabulary | **Closed — ADR-0006** | Four levels retained. The `cpic_strength`/`severity` split stays, because `HARNESS.md` V.4 makes the mapping between them a product policy decision that belongs in reviewable data with a named reviewer, not in an enum definition |
| 7 | FHIR gene scope | **Resolved — ADR-0003** | Unmapped genes are imported as explicit unknowns with the original text preserved; a diplotype is never invented. Any assessment depending on one halts |
| 8 | Engine B timing and reviewer | Open, out of scope | Engine B is excluded from this feature. The `ToolAdapter` interface is built to the shape Engine B will need, which is the whole reason the interface exists |
| 9 | pgvector on the chosen managed Postgres | Open — deployment, not build | Dev and CI use the `pgvector/pgvector:pg16` image via testcontainers, so the build is unaffected. Confirm before the production host is chosen |
| 10 | Structured-output support for the specific model | **Answered by measurement** | The OpenAI-compatible layer does not guarantee schema conformance and ignores `strict`. Rather than assert a fidelity level, schema parse-failure rate is a reported metric (ADR-0005), with a defined fallback to the native provider SDK behind the same protocol |
| 11 | Host capability for a second service | **Open** | The PharmCAT service is required, not optional, and ADR-0007 adds a CYP2D6 caller if the VCF path ships. This constraint should drive the hosting choice rather than the reverse |

Five remain open, one of them (the clinical reviewer) external. None blocks Phase 0 through Phase 4
— that is, none blocks the four steps that remove most of the clinical risk. The only remaining
Phase 5 blocker is the licence half of decision 3.

## 3. Technical findings the plan depends on

### F-1 · The database cannot be mocked

Two of the enforcement mechanisms this plan relies on live in the database rather than in Python:
the `phenotype_calls` `CHECK ((kind='known') = (term IS NOT NULL))` constraint, which is what makes
the fail-open default unreintroducible even by direct SQL, and
`severity_policy_rows.provisional GENERATED ALWAYS AS (reviewed_by IS NULL) STORED`, which is what
keeps provisional status from drifting out of sync with reality. A mocked database exercises neither.
`testcontainers` with a real PostgreSQL 16 + pgvector image is therefore a correctness requirement
for Principles II and V, not a testing preference.

### F-2 · Measurement must precede replacement, which is why the legacy tree survives Phase 1

Delivery step 1 says "measure the current engine honestly", which reads oddly against a rebuild. The
resolution, already recorded in the spec and in PHR 0003: the golden set and the scoring are
deliberately engine-independent — written against published guideline tables, not against any
implementation — so they are the durable asset and outlive the code under test. Running them once
against the outgoing implementation is cheap and produces the "before" figure that makes the
replacement's improvement demonstrable rather than asserted.

Two consequences for sequencing: the legacy tree and the outgoing provider dependency must not be
removed before Phase 1 completes, and Phase 0's ablation switch and network removal must land before
Phase 1 starts, or the baseline measures a non-deterministic, covertly model-assisted engine.

### F-3 · The two amendments must land before implementation, not alongside it

The constitution's supremacy clause makes `HARNESS.md` the governing document and requires the
constitution to be amended in the same pull request when they diverge. Both divergences in section 1
are known now. Writing code against a spec line that cannot be built (`temperature=0`) or against a
framework the spec does not name (Agents SDK vs LangGraph) would be routing around the amendment
procedure rather than following it.

### F-4 · No latency target exists and none may be invented

`HARNESS.md` sets no performance goal for Engine A, and FR-042 forbids publishing an unmeasured
figure as though it were measured. The plan therefore states no latency target. If one is needed
later it must be measured first and dated, like every other number in this project.

## 4. What was deliberately not researched

The stack was fixed in advance. Database choice, driver, migration tool, embedding library,
retrieval strategy, container topology, typing and lint tooling, and the test stack were all settled
by `HARNESS.md` IX.1 and the owner's plan input, and are recorded in plan.md's Technical Context
without re-derivation. Re-opening them would be work that produces no decision.

---

*Research and education only. Synthetic data only. Not a medical device.*
