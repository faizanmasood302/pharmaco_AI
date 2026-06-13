# Pharmacogenomic (PGx) Agent Harness

**Research simulation for precision prescribing and experimental therapy design. Not for clinical use.**

The Pharmacogenomic Harness is a dual-pipeline prototype for auditable pharmacogenomic decision support and N-of-1 therapy research simulation. It uses synthetic demo data, deterministic guardrails, and human review gates to explore workflows before any real clinical compliance work.

## Current Prototype Scope

| Pipeline | Purpose | Key Agents |
| :--- | :--- | :--- |
| **Standard Care Simulation** | PGx evaluation over demo patient profiles | Analyst, Critic, Reporter |
| **N-of-1 Research Simulation** | Experimental therapy design workflow | Design, Validation, Critic |

- **FHIR R4 parsing:** Built-in parsers extract patient demographics, genomic (`CYP2D6`, etc.) phenotypes, and `MedicationRequest` resources from sample bundles.
- **Human review gate:** Agent outputs remain behind explicit human approval in the demo workflow. This is a prototype control, not validated regulatory compliance.
- **Synthetic data only:** Never process real PII or PHI in this repository or its local demo environments.

## Tech Stack

- **Backend:** Python, FastAPI, LangGraph-style agent orchestration.
- **Frontend:** Next.js, TypeScript, React.
- **Data and memory:** Supabase/PostgreSQL for state, plus a markdown clinical-logic vault.
- **Security:** BetterAuth sessions, backend session verification, and Supabase Row-Level Security policies for clinical tables.

## Model Strategy

The harness is model-agnostic. Current code is optimized for prototype workflows; the options below are roadmap candidates, not clinical validation claims.

| Model / Provider | Best Used For | Why |
| :--- | :--- | :--- |
| **Groq / Llama** | UI prototyping and demos | Low latency for chained agent steps. |
| **GPT-4o** | Future standard-care evaluation | Strong structured-output support for dashboard contracts. |
| **Claude** | Future N-of-1 research comparison | Strong long-context reasoning over dense scientific literature. |
| **MedLM / Gemini on Vertex AI** | Future clinical deployment evaluation | Candidate path for healthcare integrations after formal validation. |

## Architecture

The stale architecture image link has been removed from this README. See [ARCHITECTURE.md](ARCHITECTURE.md), [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md), and [FUTURE_ARCHITECTURE.md](FUTURE_ARCHITECTURE.md) for the current architecture and roadmap.

## Getting Started

1. Clone the repo: `git clone https://github.com/faizanmasood302/pharmaco_AI.git`
2. Copy environment templates into `agent-server/.env` and `web/.env.local`.
3. Run the stack: `docker-compose up --build`

## Security

This harness uses **synthetic demo data only**. Never process real PII or PHI. See [SECURITY.md](SECURITY.md) for vulnerability reporting.
