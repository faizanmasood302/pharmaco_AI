# ADR-0004: Anthropic as LLM provider, official SDK, no orchestration framework

**Status**: Accepted; the orchestration portion superseded by [ADR-0005](./0005-agent-framework.md) on 2026-08-23. The provider decision (Anthropic, `claude-opus-5`, behind `LlmClient`) stands.
**Date**: 2026-08-22
**Decider**: M. Faizan (project owner)
**Constitution reference**: Governance — open decisions; Principles I and IV; IX.0 rule 1
**Spec reference**: `specs/001-pgx-safety-harness/spec.md` FR-043, FR-044, FR-045, FR-046,
User Story 9

## Context

The outgoing system calls Groq (`llama-3.3-70b-versatile`) directly through a hand-rolled tool loop,
with two known defects: `parse_opinion` extracts JSON from prose with a regex and returns `{}` on
failure, and the tool loop appends one synthetic assistant message per tool call rather than one
message carrying all calls. Both are Part VIII failure-catalogue patterns.

Three orchestration packages were considered and one was already installed. An audit of the tree
found `langsmith>=0.8.0` declared as a dependency with **zero imports anywhere in the project**,
despite commit `ff6a9c5` being titled "feat(tracing): add LangSmith observability + drift
monitoring." The commit claimed a layer that did not exist.

The constitution constrains this decision in two directions. Principle IV requires the entire AI
layer to be removable, so no core path may depend on a provider. IX.0 rule 1 states that fewer
moving parts wins, and the MCP layer already demonstrated the cost of a decorative abstraction: it
could have been entirely broken with no observable difference.

## Decision

**Provider: Anthropic.** **SDK: the official `anthropic` Python SDK.** **Default model:
`claude-opus-5`.**

All provider access goes behind an internal `LlmClient` protocol. No provider SDK may be imported
outside the AI layer.

**No orchestration framework.** LangChain, LangGraph and LangSmith are all rejected:

| Package | Disposition | Reason |
|---|---|---|
| LangChain | Rejected permanently | Generic chain/prompt/retriever glue. Retrieval is Postgres queries; prompts are our own. Adds surface, solves nothing here |
| LangGraph | Deferred, not rejected | Real value for branching state machines and replay. The pipeline is near-linear: validate → assess → retrieve → explain → gate. Plain async Python covers it. Revisit if the graph genuinely branches |
| LangSmith | Removed | Third-party LLM tracing. The constitution already replaces it with `RunManifest` rows — prompt hash, response hash, gate verdict — in our own database, keeping the clinical audit trail out of a third party's cloud |

Replacements for what those packages would have provided:

| Need | Solution |
|---|---|
| Orchestration | Plain async Python |
| Tracing | `RunManifest` rows in Postgres (constitution requirement) |
| Structured output | SDK-native `output_config: {format: …}` / `client.messages.parse()` with Pydantic |
| Tool loop | SDK tool runner (`@beta_tool` + `client.beta.messages.tool_runner`) |

### Sequencing

Dependency changes are deliberately staged rather than done at once:

1. **`langsmith` removed now.** Zero imports, zero risk. Done 2026-08-22; 76 tests still pass.
2. **`anthropic` added when the first code that imports it is written — not before.** Adding an
   unused dependency now would recreate exactly the phantom-dependency defect this ADR removes.
3. **`groq` retained until the baseline is measured.** The outgoing engine must stay runnable to
   produce the "before" concordance figure that makes the rebuild's improvement demonstrable
   (User Story 1). Removing it early destroys that measurement.

## Consequences

**Accepted:**

- SDK-native structured output deletes `parse_opinion` entirely. Clinical meaning is never again
  recovered from prose by regex.
- The SDK tool runner removes the hand-rolled loop and the parallel-tool-call defect with it.
- Tracing stays in our own Postgres, which is a stronger position for clinical data than a
  third-party SaaS and satisfies the provenance requirements directly.
- Three fewer dependencies than the HARNESS stack proposed, consistent with IX.0 rule 1.

**Costs, accepted knowingly:**

- Higher token cost than Groq/Llama. Accepted as the owner's decision; see alternatives.
- The tool runner is a beta SDK surface and may change.
- Deferring LangGraph means `RunManifest` replay is hand-built if it is ever needed.

### Model-specific constraints that follow

`claude-opus-5` has a narrower request surface than older models. These are hard constraints, not
preferences:

- **`temperature`, `top_p`, `top_k` are removed** — sending any of them returns 400.
- **`budget_tokens` is removed** — returns 400. Thinking is adaptive and on by default.
- **Assistant prefill returns 400.** Response shaping uses structured outputs or the system prompt.
- Depth is controlled by `output_config: {effort: …}` (`low`–`max`, default `high`).
- Tool inputs must be parsed with `json.loads()`; escaping varies.
- All `tool_result` blocks for parallel calls go in **one** user message.

**This conflicts with `HARNESS (1).md` IX.1**, which specifies *"Settings: `temperature=0`, seed
where supported."* That line is unimplementable on Opus 5 and must be amended. Determinism of the
LLM layer was never claimed anyway — the constitution covers it by narrative rejection and omission
rates, not reproducibility — so the amendment removes a setting, not a guarantee.

## Alternatives considered

**Stay on Groq with `llama-3.3-70b-versatile`.** Meaningfully cheaper and faster, and defensible:
the grounding gate is designed to catch a weaker model's failures regardless of which model produces
them. Rejected by owner decision to change provider. The `LlmClient` protocol keeps this reversible
as a configuration change.

**Claude Sonnet 5 (`claude-sonnet-5`, $3/$15 per MTok) or Haiku 4.5 (`claude-haiku-4-5`, $1/$5).**
Available as deliberate cost choices. Not adopted as the default: selecting a cheaper tier is a
product decision for the owner, not an engineering default, and the narrative work sits behind a
strict gate where instruction-following quality directly determines the rejection rate. Revisit once
the rejection rate is measured — if Opus 5 and a cheaper tier produce comparable rejection rates,
the cheaper tier is the better choice on evidence rather than on assumption.

**LangGraph now.** Rejected on timing. Adopting orchestration before the pipeline exists risks
building the graph around the framework rather than the domain.

## Revisit when

- The first narrative rejection and omission rates are measured, making a model-tier comparison
  evidence-based rather than speculative.
- The pipeline develops genuine branching or requires replay, at which point LangGraph is
  reconsidered on merit.
- The tool runner leaves beta, or its API changes.
