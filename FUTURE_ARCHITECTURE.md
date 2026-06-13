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

**Current State:** The system uses custom python scripts (e.g., `fhir/parser.py`) for data parsing and lacks real-world NLP or PHI scrubbing tools.

**Future State:** In the agentic architecture, tools are functions the agents can call. Google Cloud provides enterprise-grade tools that can replace custom Python scripts:

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
*   **Current State:** Prototype implementation only.
*   **Future State:** Move from 9 demo drugs to 50+ high-impact medications.
*   **Focus:** Ingest CPIC guidelines for SSRIs (Antidepressants) and Statins (Cholesterol).
*   **Implementation:** Update `agent-server/pgx/rules.py` with deterministic logic for these new classes to cover the most common primary care prescriptions.

### Track 2: The "Reasoning Trace" UI (Observability)
*   **Current State:** Prototype implementation only.
*   **Future State:** Provide transparency into the AI's internal "argument" process.
*   **Implementation:** Add a **"Review Flow"** tab to the `EvaluationPanel.tsx` that displays the internal dialogue between the Reasoning Agent and the Critic Agent. This builds clinical trust by eliminating "Black Box" AI.

### Track 3: Interactive Adherence Lab (Patient Engagement)
*   **Current State:** Prototype implementation only.
*   **Future State:** Transition from static monitoring to an active patient management platform.
*   **Implementation:** Complete the `process_check_in` backend logic and build a **"Patient Simulator"** in the web UI. This allows for testing dose misses or side-effect alerts in real-time.

### Track 4: Multi-Model Evaluation (Performance)
*   **Current State:** Prototype implementation only.
*   **Future State:** Quantify the speed vs. safety trade-offs of different "Brains."
*   **Implementation:** Implement a backend toggle between **Llama 3 (Groq)** and **GPT-4o (OpenAI)** and benchmark accuracy against the `pgx/rules.py` deterministic baseline.

### Track 5: Real-World Bioinformatics Heavy-Lifting
*   **Current State:** Prototype implementation only.
*   **Future State:** Replace mock physics scores with actual biological computations.
*   **Implementation:** Integrate `bioinformatics_adapter.py` with actual scientific API clusters (e.g., EBI, NCBI) to run **ViennaRNA** for MFE, **BLAST** for homology, and **AlphaFold** for protein structural analysis.

### Track 6: Advanced PHI De-identification (Local Layer)
*   **Current State:** Prototype implementation only.
*   **Future State:** Ensure zero-leakage of PHI when using cloud-based LLMs.
*   **Implementation:** Implement a local NLP "PII-Scrubber" that strips identifying markers (Names, DOBs, MRNs) *before* data is sent to external inference providers.

---

# Advanced Agentic Patterns (Future Horizon)

To evolve the agents from "guided reasoners" to dynamic, tool-wielding experts, the architecture will eventually incorporate these advanced patterns:

### 1. The "Panel of Experts" (Multi-Agent Debate)
*   **Current State:** Standard single-agent reasoning.
*   **Future State:** Instead of a single Analyst, LangGraph spawns specialized agents (Pharmacologist, Geneticist, Primary Care) concurrently.
*   **Impact:** A Synthesis Agent forces a consensus, mimicking a clinical tumor board and drastically reducing hallucination.

### 2. Active Tool Use (Function Calling)
*   **Current State:** Standard single-agent reasoning.
*   **Future State:** Equip agents with native tools to fetch data mid-thought (e.g., `query_pubmed()`, `calculate_renal_function()`).
*   **Impact:** Moves the system from a "smart textbook" (RAG) to an active medical assistant capable of live computation and dynamic research.

### 3. Agent "Drift" & Hallucination Monitoring
*   **Current State:** Standard single-agent reasoning.
*   **Future State:** Integrate observability platforms like **LangSmith** or **Arize Phoenix**.
*   **Impact:** Real-time tracking of agent reasoning consistency. Automatically flag "Safety Critic" outputs that diverge from deterministic baselines or historical expert approvals.

### 4. Episodic Memory & Continuous Learning
*   **Current State:** Standard single-agent reasoning.
*   **Future State:** Implement Reflective Memory via a Vector Database. When a clinician rejects a recommendation, the rationale is embedded and queried during future evaluations.
*   **Impact:** The agent "learns" from the clinic's specific prescribing habits and historical corrections.

### 5. Dynamic "Plan-and-Solve" Orchestration
*   **Current State:** Standard single-agent reasoning.
*   **Future State:** A Supervisor Agent dynamically draws the LangGraph topology based on patient complexity, rather than following a hardcoded path.
*   **Impact:** Simple patients follow fast paths; complex patients trigger deep, multi-branch research topologies.

---

# Enterprise Readiness & Governance

Based on architectural reviews for high-stakes clinical deployment, the system must transition from producing "reasoning traces" to generating highly structured, auditable provenance. The following features are prioritized for regulatory compliance and enterprise safety:

### 1. SaMD Regulatory Compliance (Software as a Medical Device)
*   **Current State:** Not implemented.
*   **Future State:** Formalize the risk management framework required for FDA/EMA approval.
*   **Implementation:** Establish a formal **Hazard Analysis** and **Risk Management Plan (ISO 14971)**. Document the "Human Gate" as a critical risk mitigation for potential agent hallucinations.

### 2. SMART-on-FHIR "Write-back"
*   **Current State:** Not implemented.
*   **Future State:** Move from a read-only dashboard to a fully integrated clinical tool.
*   **Implementation:** Develop OAuth2 handshakes and `/api/ehr/write-back` endpoints to post clinical notes and prescribed candidates directly into hospital EHRs like **Epic** and **Cerner**.

### 3. Async Computational Scalability
*   **Current State:** Not implemented.
*   **Future State:** Handle long-running biological simulations without blocking the UI.
*   **Implementation:** Introduce a **Task Queue (Celery + Redis)** to manage intensive bioinformatics jobs (homology searches, MFE folding) as background tasks, providing live status updates to the frontend via WebSockets.

### 4. Evidence Provenance Graph
*   **Current State:** Not implemented.
*   **Future State:** Move away from relying on LLM narrative justification.
*   **Implementation:** Update Pydantic models so every clinical claim outputs a strict JSON structure linking it directly to the source guideline, the specific document chunk ID, and a confidence score.

### 5. Formal Medication Safety Engine
*   **Current State:** Not implemented.
*   **Future State:** Do not rely on LLMs to infer drug interactions from text.
*   **Implementation:** Expand `pgx/rules.py` into a robust, structured medication safety engine (checking contraindications, max doses, interactions) that runs *before* the LangGraph pipeline. The agents receive this structured safety payload to inform their reasoning.

### 3. Clinician Disagreement Capture
*   **Current State:** Not implemented.
*   **Future State:** Turn the "Human Gate" into an active learning mechanism.
*   **Implementation:** When a clinician rejects an AI recommendation, the system must require and structure their rationale. This disagreement data is captured, saved to the database, and fed back into the system as a continuous learning dataset.

### 4. Guideline Version Control
*   **Current State:** Not implemented.
*   **Future State:** Ensure the system knows exactly *which* authority it is citing.
*   **Implementation:** Implement timestamped, auditable tracking for all clinical guidelines (e.g., CPIC, FDA) in the RAG database, allowing the system to handle retired guidelines and resolve conflicts between different medical authorities.

### 5. Outcome Tracking
*   **Current State:** Not implemented.
*   **Future State:** Close the loop on AI recommendations.
*   **Implementation:** Build infrastructure to measure whether the AI's recommendations actually improved patient care over time, which is critical for FDA/EMA software-as-a-medical-device (SaMD) classifications.

