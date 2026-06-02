# Future Architecture: Enterprise Healthcare AI Upgrade

This document outlines the strategic upgrade path for the Pharmacogenomic (PGx) Agent Harness. The goal is to transition from the current high-speed prototyping architecture (using Groq/Llama 3 and synthetic data) to an enterprise-grade, HIPAA-compliant medical instrument suitable for real-world clinical environments.

## The Strategy: Integrating Google Cloud Healthcare APIs & MedLM

The current architecture successfully proves the concept of **Agentic Orchestration with Deterministic Guardrails**. The transition to Google's specialized healthcare models and APIs will supercharge this architecture without requiring a rewrite of the underlying LangGraph orchestration.

### 1. MedLM / Medically-Tuned Gemini as the "Agent Brain"

**Current State:** The system uses Groq (Llama 3 70B) for inference. This provides ultra-low latency, which is excellent for chaining multiple agent steps quickly in a prototype environment.

**Future State:** Swap the underlying model calls in the `Reasoning`, `Critic`, and `Reporter` agents to use Google's MedLM or medically-tuned Gemini models via the Vertex AI API.

*   **Why?** While the current system relies heavily on Source-Grounded RAG to provide medical context to a general-purpose LLM, replacing the general model with MedLM provides deeper clinical nuance. When the Critic Agent challenges a prescription, MedLM draws on its specialized medical training to evaluate the RAG data, reducing hallucinations and improving clinical safety.
*   **Multimodality:** Upgrading to Gemini allows agents to process non-text inputs (e.g., medical imaging, scanned PDFs of genetic test results) natively within the reasoning loop.

### 2. Google Cloud Healthcare APIs as "Agent Tools"

In the agentic architecture, tools are functions the agents can call. Google Cloud provides enterprise-grade tools that can replace custom Python scripts:

*   **The FHIR Tool:** Replace the custom `fhir/parser.py` with the **Google Healthcare FHIR API**. The Research Agent can use this API to seamlessly and compliantly ingest, store, and map complex hospital data (like from Epic or Cerner).
*   **The De-identification Tool (Privacy Agent):** Introduce a new agent step in the N-of-1 Research pipeline. Before sharing data for experimental therapy design, this agent calls the **Healthcare NLP API** to automatically scrub all PHI (names, addresses, dates) from clinical notes.
*   **The Medical NLP Tool:** Allow agents to process messy, unstructured doctor's notes. The agent can call the Healthcare Natural Language API to instantly extract medications, dosages, and genomic markers into structured JSON for the reasoning loop.

### 3. Data & Regulatory Compliance

*   **Current State:** The system is explicitly restricted to Synthetic Demo Data.
*   **Future State:** To process real Patient Health Information (PHI), the infrastructure must be deployed within a secure Google Cloud VPC.
    *   Execute Business Associate Agreements (BAAs) with Google Cloud.
    *   Implement database encryption-at-rest.
    *   Enable strict audit logging and retention policies through Google Cloud Audit Logs.

### 4. Expanding the Formulary

*   **Current State:** The deterministic reasoning fallback relies on a hardcoded demo formulary of ~9 medications.
*   **Future State:** Integrate the system with a comprehensive, live pharmacological database like **RxNorm** or **First Databank (FDB)** to handle real-world polypharmacy and multi-drug interaction checks.

### 5. Multi-Model Strategy: Groq vs. Claude vs. GPT

The architecture is designed to be model-agnostic. While currently optimized for Groq (Llama 3), switching to other frontier models provides specific trade-offs:

| Model / Provider | Primary Benefit | Impact on System |
| :--- | :--- | :--- |
| **Groq (Llama 3)** | **Extreme Latency** | Ideal for high-speed agentic chains. Lowers cost but may have slightly higher hallucination rates in complex clinical logic. |
| **GPT-4o (OpenAI)** | **Structured Reliability** | Supports "Structured Outputs" to guarantee valid JSON formatting for the clinical dashboard 100% of the time. |
| **Claude 3.5 (Anthropic)** | **Nuance & Comprehension** | The current gold standard for complex medical reasoning and reading massive patient histories (large context window). |
| **Gemini (Google)** | **Multimodality** | Required for future versions that need to "see" medical imaging or parse scanned lab results natively. |

### Summary

The transition to Google's Healthcare suite will not break the existing multi-agent architecture; it will act as a massive capability injection. The orchestration logic remains intact, while the "brains" become medically certified and the "tools" become enterprise-grade, paving the way for eventual clinical validation and use.

---

# Upcoming Sprint: Clinical Depth & Agent Observability

Following the completion of the foundational infrastructure, the next development phase (Sprint 2) focuses on transforming the technical demo into a robust clinical instrument.

### Track 1: Expanding the Medical Knowledge Base (Depth)
*   **Goal:** Move from 9 demo drugs to 50+ high-impact medications.
*   **Focus:** Ingest CPIC guidelines for SSRIs (Antidepressants) and Statins (Cholesterol).
*   **Implementation:** Update `agent-server/pgx/rules.py` with deterministic logic for these new classes to cover the most common primary care prescriptions.

### Track 2: The "Reasoning Trace" UI (Observability)
*   **Goal:** Provide transparency into the AI's internal "argument" process.
*   **Implementation:** Add a **"Review Flow"** tab to the `EvaluationPanel.tsx` that displays the internal dialogue between the Reasoning Agent and the Critic Agent. This builds clinical trust by eliminating "Black Box" AI.

### Track 3: Interactive Adherence Lab (Patient Engagement)
*   **Goal:** Transition from static monitoring to an active patient management platform.
*   **Implementation:** Complete the `process_check_in` backend logic and build a **"Patient Simulator"** in the web UI. This allows for testing dose misses or side-effect alerts in real-time.

### Track 4: Multi-Model Evaluation (Performance)
*   **Goal:** Quantify the speed vs. safety trade-offs of different "Brains."
*   **Implementation:** Implement a backend toggle between **Llama 3 (Groq)** and **GPT-4o (OpenAI)** and benchmark accuracy against the `pgx/rules.py` deterministic baseline.
