# ADR-0005: OpenAI Agents SDK as the agent layer, `as_tool()` composition only

**Status**: Accepted
**Date**: 2026-08-23
**Decider**: M. Faizan (project owner)
**Constitution reference**: Principle I; Architectural Constraints (import contract, bounded agent
roles); Governance — open decisions
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-001, FR-002, FR-003, FR-025, FR-029
**Supersedes**: the "no orchestration framework" portion of [ADR-0004](./0004-llm-provider-and-sdk.md)
**In force since**: 2026-08-23, on amendment of `HARNESS.md` IX.1 (orchestration row, settings row),
IX.6 (pin list) and the MANIFEST AI-layer table, with the constitution's matching pin sentence and
layer-contract rename in `HARNESS.md` v1.1 / constitution v1.0.1

## Context

Three positions on the agent layer existed at the same time, and they disagreed.

`HARNESS.md` IX.1 specifies **LangGraph** — "typed state, conditional edges, checkpointing that
backs `RunManifest` replay." ADR-0004, decided a day later, rejected all orchestration frameworks
and chose **plain async Python**, reasoning that the pipeline is near-linear (validate → assess →
retrieve → explain → gate) and that a decorative abstraction is a cost the MCP layer had already
demonstrated. The plan input for feature 001 names the **OpenAI Agents SDK**, restricted to
`Agent.as_tool()`, with `handoff()` prohibited and no tool permitted to wrap an engine call.

Leaving that unresolved would mean writing the plan against whichever source the reader reached
first. The constitution forbids picking one silently.

Two defects in the outgoing implementation bear on the choice, both catalogued in `HARNESS.md`
Part VIII. `agents/base.py::parse_opinion` regexes a JSON object out of prose and returns `{}` on
failure — clinical meaning derived from free text. The same file's tool loop appends one synthetic
assistant message *per* tool call inside the iteration, instead of one assistant message carrying
all calls followed by all results together, which silently suppresses parallel tool calling. ADR-0004
proposed to fix both by hand.

## Decision

**The agent layer is built on the OpenAI Agents SDK (`openai-agents`), with four restrictions that
are part of the decision, not implementation detail:**

1. **`Agent.as_tool()` composition only.** A called agent receives generated input, returns a typed
   result, and returns control to its caller.
2. **`handoff()` is prohibited.** It transfers control of the run.
3. **No tool wraps an engine call.**
4. **SDK tracing is disabled**, and schema parse-failure rate is measured.

**The provider decision from ADR-0004 stands unchanged**: Anthropic, `claude-opus-5`, behind the
internal `LlmClient` protocol. Reached through the SDK's LiteLLM extension
(`openai-agents[litellm]`, `LitellmModel` / `LitellmProvider`), which exists precisely to route
Agents-SDK runs to non-OpenAI providers. The framework being OpenAI's does not make the provider
OpenAI's, and no provider SDK is imported outside `src/ai/`.

### Why each restriction is load-bearing

**`as_tool()` rather than `handoff()`** is the difference between an agent that answers a question
and an agent that takes over. `handoff()` hands the conversation to another agent, which is the
mechanism by which an agent would come to route a clinical judgment — the shape Principle I exists
to prevent. `as_tool()` returns control after each call, so the orchestration remains ours.
Prohibiting `handoff()` makes Principle I structural rather than behavioural: there is no configuration
in which control leaves the caller.

**No tool wrapping an engine call** keeps the import contract meaningful. `src/ai/agents/` may not
import `src/engines/`; a tool that called `assess()` from inside the agent layer would be that
violation wearing a different name. Agents receive already-computed `Assessment` objects and return
narrative. They have no way to invoke, influence, or re-run a judgment — which is also what makes
every agent trivially unit-testable against a fixture.

**Structured output is not guaranteed, so it is measured.** The OpenAI-compatible layer used for
structured output does not guarantee schema conformance — the `strict` parameter for function
calling is ignored. Schema parse-failure rate MUST therefore be a measured metric, reported
alongside the narrative refusal and omission rates. If it proves material, the narrative agents move
to the native provider SDK behind the `LlmClient` protocol, with no change above that protocol.

This is the same discipline the rest of the project applies to every other claim: the SDK's typed
`output_type` is an improvement on regexing JSON out of prose, but an improvement whose size is
unmeasured is not a guarantee. Measuring it is also what makes the fallback decidable rather than a
matter of impression.

**Tracing disabled** (`set_tracing_disabled(True)`). The SDK exports traces to a third party by
default. That would send clinical narrative and patient context out of our control and would
duplicate, worse, the `run_manifests` and `narratives` tables that exist to keep the audit trail in
our own Postgres. This is the same reasoning that removed LangSmith in ADR-0004; adopting the SDK
without disabling tracing would reintroduce exactly what that decision removed.

### What this buys over plain async Python

| Defect ADR-0004 would have hand-fixed | What the SDK provides |
|---|---|
| `parse_opinion` regexing JSON out of prose, `{}` on failure | Typed `output_type` — a schema-validated result or a raised error, never a silently empty dict |
| A tool loop that suppresses parallel tool calling | The SDK's own loop, maintained upstream |
| Per-agent model selection and turn budgets, hand-rolled | `RunConfig`, `max_turns`, per-agent model pinning |

### Alternatives considered

| Option | Disposition |
|---|---|
| **LangGraph** (`HARNESS.md` IX.1) | Deferred, not rejected — unchanged from ADR-0004. Its value is checkpointed typed state for branching graphs; this pipeline is near-linear. Revisit if the graph genuinely branches or if `RunManifest` replay needs checkpointing the manifest cannot provide |
| **Plain async Python** (ADR-0004) | Superseded. It is not wrong, but it leaves the structured-output and tool-loop defects to be rebuilt by hand, which is how they arose the first time |
| **LangChain** | Rejected permanently. Unchanged from ADR-0004 |
| **OpenAI Agents SDK with `handoff()` available** | Rejected. An available `handoff()` is a route by which a future contributor moves a judgment into the agent layer without the build objecting |

## Consequences

- `agents/base.py` is deleted rather than repaired, `parse_opinion` with it.
- One dependency is added (`openai-agents[litellm]`) against three that ADR-0004 removed or
  rejected. IX.0 rule 1 — fewer moving parts wins — is satisfied on net.
- The prohibitions must be enforced, not just written down. Phase 6 adds a check that `handoff` is
  not imported anywhere under `src/ai/`, alongside the `import-linter` contract that already
  prevents `src/ai/agents/` from reaching `src/engines/`.
- `openai-agents` is added **when the first importing code is written**, not now. Adding an unused
  dependency would recreate the phantom-dependency defect ADR-0004 exists to remove.
- Tracing configuration is a correctness assertion, so it gets a test rather than a comment.
- Schema parse-failure rate joins the measured metrics in `eval/`, reported per release beside
  narrative refusal and omission rates.

## The conflict this created, and how it was resolved

`HARNESS.md` IX.1 named LangGraph, and the constitution's supremacy clause makes `HARNESS.md`
governing, so this ADR was recorded but not in force until the source document was amended.

**That amendment landed on 2026-08-23** (plan item P0-1), grouped with the ADR-0004 amendment
removing `temperature=0` and `seed`, since both edited the same two tables:

- `HARNESS.md` IX.1 orchestration row → OpenAI Agents SDK, `as_tool()` only, `handoff()` prohibited,
  tracing disabled. Rationale recorded in the row itself: every clinical value is computed outside
  the agent layer, so what remains is a few stateless agents producing narrative and inquiry, and a
  graph runtime is ceremony for that shape.
- `HARNESS.md` IX.1 settings row and IX.6 pin list → sampling parameters removed.
- `HARNESS.md` MANIFEST AI-layer table → `openai-agents`; provider row brought into line with
  ADR-0004.
- `ai/graph` renamed `ai/orchestration` in `HARNESS.md` IV.8, IV.11 and IX.7, and in the
  constitution's Architectural Constraints table. There is no graph module. The rename does not
  change the contract: same layer, same permitted and forbidden edges.
- `HARNESS.md` v1.0 → v1.1 with an amendment log; constitution v1.0.0 → v1.0.1 (PATCH) with a Sync
  Impact Report.

This decision is now in force.

## Revisit when

- The pipeline acquires real branching or needs replay from a checkpoint — LangGraph becomes
  arguable again.
- Structured output through the LiteLLM layer proves lower-fidelity than through the provider SDK
  directly (open decision 10, verified at Phase 6). If so, the fallback is the provider SDK behind
  the same `LlmClient` protocol, with the SDK retained only for composition.
- The SDK's default tracing behaviour changes in a way that makes disabling it insufficient.
