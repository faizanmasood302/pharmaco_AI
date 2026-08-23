---
id: 0005
title: Amendments And Open Decisions
stage: plan
date: 2026-08-23
surface: claude-code
model: claude-opus-5
feature: pgx-safety-harness
branch: 001-pgx-safety-harness
route: history/prompts/pgx-safety-harness/
supersedes: 0004
artifacts:
  - HARNESS.md
  - .specify/memory/constitution.md
  - docs/adr/0005-agent-framework.md
  - docs/adr/0006-severity-scale.md
  - docs/adr/0007-cyp2d6-structural-variant-coverage.md
  - specs/001-pgx-safety-harness/plan.md
  - specs/001-pgx-safety-harness/research.md
  - specs/001-pgx-safety-harness/data-model.md
  - specs/001-pgx-safety-harness/quickstart.md
  - specs/001-pgx-safety-harness/spec.md
  - CLAUDE.md
status: complete — HARNESS.md v1.1, constitution v1.0.1, six of eleven open decisions closed
links:
  - specs/001-pgx-safety-harness/plan.md
  - docs/adr/0004-llm-provider-and-sdk.md
  - history/prompts/pgx-safety-harness/0004-implementation-plan.md
---

# PHR 0005 — Amendments And Open Decisions

## Stage

`plan` — discharging the amendments PHR 0004 left pending, and closing three open decisions.

## Prompt (verbatim)

```text
1. Amend HARNESS.md Part IX.1 — orchestration row.
Replace LangGraph with the OpenAI Agents SDK. The LangGraph entry is stale. Rationale: this architecture keeps every clinical value outside the agent layer, so what remains is a small number of stateless agents producing narrative and inquiry. A graph runtime is ceremony for that; the SDK's guardrail primitives are the closer fit. Group this with the temperature=0 / seed amendment ADR-0004 already flagged, since both edit the same tables.

2. Amend HARNESS.md — layer contract table.
Rename ai/graph to ai/orchestration everywhere it appears, including in the constitution's Architectural Constraints table. There is no graph module.

3. ADR-0005 is approved as written, including the fourth restriction (SDK tracing disabled). Add this clause before marking it in force:

The OpenAI-compatible layer used for structured output does not guarantee schema conformance — the strict parameter for function calling is ignored. Schema parse-failure rate MUST therefore be a measured metric reported alongside narrative refusal and omission rates. If it proves material, the narrative agents move to the native provider SDK behind the LlmClient protocol, with no change above that protocol.

4. Close open decision 6 — severity scale.
Four levels retained (low / moderate / high / critical). Rationale: the golden set, spec, and policy table all assume four; changing it later rewrites all three, and there is no measured reason to change it now. Revisit only if measurement shows the CPIC-to-severity mapping loses information. Record as an ADR.

5. Close open decision 3 — PharmCAT coverage.
Licence terms still need verification, but the coverage gap is already known and must be decided now, not discovered at test time: PharmCAT does not call copy-number or complex structural variants. CYP2D6 gene duplication is what produces an ultra-rapid metabolizer — the flagship codeine case. Under the project's own "uncovered means no guidance" rule, that case returns NO_GUIDANCE with PharmCAT alone.

Decide and record one of:

(a) Phase 5 adds a second caller (PyPGx or StellarPGx) for CYP2D6 only, behind the same adapter interface; or
(b) CYP2D6 ultra-rapid is explicitly out of scope for v1, golden case P-2D6-005 is marked expected-NO_GUIDANCE, and the limitation is stated in user-facing documentation.

6. Phase 0 stays ahead of Phase 1. Do not reorder. Measuring an engine that can still reach the network produces a figure that varies between runs and is partly model-derived — worse than no baseline, because it would be cited.

7. The reference concordance harness is now in the repo at eval/. It is Phase 1's starting shape, not a design to redesign.
```

## Response

### Items 1–3: amendments landed

`HARNESS.md` v1.0 → **v1.1**, with an amendment log added at the foot of the file:

| Change | Where |
|---|---|
| Orchestration row: LangGraph → OpenAI Agents SDK, `as_tool()` only, `handoff()` prohibited, tracing disabled | IX.1 AI layer |
| Settings row: `temperature=0` / seed → "not settable on the pinned model", with the schema parse-failure metric named in its place | IX.1 AI layer |
| Pin list: sampling parameters removed; the model identifier alone is pinned | IX.6 |
| MANIFEST AI-layer table: `langgraph` → `openai-agents`; provider row brought into line with ADR-0004 (was still "Groq"); `instructor` removed as superseded by typed `output_type` | MANIFEST |
| `ai/graph` → `ai/orchestration` | IV.8 tree, IV.8 import contract, IV.11 lifecycle, IX.7 topology diagram |

Constitution v1.0.0 → **v1.0.1** (PATCH), with a second Sync Impact Report: the layer-contract table
rename and the `RunManifest` pin sentence. Recorded as PATCH rather than MAJOR deliberately, and the
reasoning is in the report — the rename leaves the contract identical (same layer, same permitted
and forbidden edges), and removing two parameters that were never settable weakens no guarantee,
since determinism was never claimed for the LLM layer.

The MANIFEST provider row was not in the requested list. It still said "Groq / OpenAI-compatible",
which ADR-0004 had already superseded, and it sits two rows from one I was editing. Corrected and
logged rather than left as a contradiction next to a fresh edit.

**ADR-0005** now carries the structured-output clause verbatim and is marked **in force**, with the
amendment recorded in it. The restriction count was corrected from three to four, since tracing is
now enumerated rather than folded into a subclause.

### Item 4: ADR-0006 — four-level severity scale

Recorded as chosen rather than defaulted, with your rationale, plus one point worth having on the
record for a future reader: the `cpic_strength`/`severity` split is not redundant translation.
`HARNESS.md` V.4 states that mapping "Strong recommendation to avoid" to "block this prescription"
is a **product policy decision, not a fact**. Collapsing the two columns would move that judgment out
of reviewable data and into an enum definition, where no pharmacist signs it — the same class of
error as deriving severity from prose. Revisit trigger recorded as you specified, and made checkable
from the per-gene and per-drug-class breakdown.

The spec's Assumptions entry ("until an architecture decision record says otherwise") is now
discharged and cites the ADR.

### Item 5: ADR-0007 — chose (a), with a narrower scope than either option assumed

**Your premise is correct, but narrower than stated, and the difference decides the question.**

PharmCAT does not call CNV or structural variants — confirmed. But it **accepts CYP2D6 diplotypes as
outside calls** (`-po`), and the workflow its own documentation recommends is exactly that: a
specialised caller determines the diplotype, PharmCAT's Phenotyper translates it. `HARNESS.md` V.3
already names this as this project's path — "Outside-call files accept diplotypes determined
elsewhere — exactly your fixture and FHIR path."

So the gap is **VCF-derived CYP2D6 only**. A duplication diplotype supplied as structured data
flows through today; one we would have to infer from a VCF does not.

That makes (b) wrong: marking `P-2D6-005` expected-`NO_GUIDANCE` and publishing the limitation would
encode a constraint the system does not have on its primary input path. Overstating a gap is a
smaller error than hiding one, but it is still a false statement about the system.

**Decision: (a), scoped to the VCF path only.** PyPGx as the caller (runs from VCF plus depth, no
WGS/BAM pipeline needed), StellarPGx as the named fallback since PharmCAT documents it with a worked
example. Behind the same `ToolAdapter`, producing a diplotype for PharmCAT to phenotype rather than a
phenotype of its own — the authority stays in one place.

`P-2D6-005` keeps its expected `ACTIONABLE`/`critical`. A **companion VCF-sourced case** is added,
expected `HALTED` until the caller lands. That keeps the gap in the scorecard rather than in a
document, and makes closing it a measurable event.

One thing is owed rather than assumed: PharmCAT's docs confirm it translates outside calls to
phenotypes but do not explicitly state that the Phenotyper assigns UM from a supplied `*1/*2x2`.
That behaviour is what the scoping rests on, so it is recorded as **P5-8, an acceptance check before
the adapter is written** — not an assumption to build on. If it fails, the scoping is wrong and the
caller is needed on every path.

The licence half of decision 3 stays open and still blocks Phase 5, now covering PyPGx as well.

### Item 6: acknowledged, no change

Phase 0 remains ahead of Phase 1. The plan already carried the reasoning as an explicit Constitution
Check point.

### Item 7: eval/ is not in the tree

**No `eval/` directory exists** — not at the repository root, not under `agent-server/`, and nothing
matching it in `git status`. Checked before writing anything that would depend on it. Phase 1 is
unchanged and still written around adapting the supplied harness; it remains that phase's first
input. If it was committed on another branch or not yet pushed, it has not reached this working tree.

### Propagation

`plan.md` (status, header versions, divergence section, Phase 0/1/5/6/9 tables, open-decisions
table), `research.md` (D-1, D-2, the decision disposition table), `data-model.md` (severity note,
`Narrative.schema_parse_ok`, the CYP2D6 VCF validation rule), `quickstart.md` (metrics,
`CYP2D6_CALLER_URL`), `spec.md` (Assumptions, Resolved Decisions), `CLAUDE.md` (versions, stack
notes, open-decision count).

## Deviations

Spec-kit scaffolding still absent; `create-phr.sh` does not exist, so this file was written directly
with the ID allocated by inspecting the directory. Same fallback as PHRs 0002–0004.

## Follow-ups

1. **`eval/` is missing.** Phase 1 cannot start without it.
2. **Licence verification** for PharmCAT and now PyPGx — the last blocker on Phase 5.
3. **Open decision 1**, the named clinical reviewer, remains a blocking external dependency. Until a
   pharmacist signs the severity table, every row is provisional.
4. Four other decisions stay open: criterion 1 IVD boundary, Engine B timing and reviewer, pgvector
   on the chosen managed Postgres, and host capability for a second service — which now means two
   services beyond the app if the VCF path ships.
5. `/sp.tasks` is the next step.
6. Nothing is committed. Seventeen artifacts plus the dependency change are outstanding on this
   branch.
7. The HuggingFace token in the `hf` remote URL is still unrotated.

## Suggested commit

```text
docs: amend HARNESS to v1.1 and constitution to v1.0.1; add ADR-0005..0007
```
