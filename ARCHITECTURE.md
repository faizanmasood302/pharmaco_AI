# System Architecture: Pharmacogenomic (PGx) Harness

This document describes the high-level architecture of the Pharmacogenomic Agent Harness, a clinical instrument for personalized prescribing and N-of-1 research.

## 1. Design Philosophy
The system is built on the principle of **Agentic Orchestration with Deterministic Guardrails**. Instead of relying on a single large language model (LLM) for medical decisions, the harness decomposes clinical workflows into specialized agents, each governed by source-grounded evidence and deterministic biological rules.

## 2. System Components

### 2.1 Backend: FastAPI Agent Server
The core intelligence layer, implemented in Python, provides:
- **Multi-Agent Orchestration:** Linear and cyclic (graph-based) workflows.
- **Source-Grounded RAG:** A retrieval engine that pulls evidence from local clinical guidelines (CPIC, PharmGKB).
- **Bioinformatics Adapter:** Simulations for mRNA folding energy (MFE), homology, and immunogenicity.

### 2.2 Frontend: Next.js Clinical Dashboard
A React-based professional interface featuring:
- **Prescription Console:** Real-time risk assessment for drug-gene pairs.
- **N-of-1 Research Workspace:** An iterative lab environment for custom therapy design.
- **Adherence Triage:** Real-world patient feedback loop with AI-driven clinical triage.

### 2.3 Storage Layer: Supabase & Obsidian
- **Supabase (Relational):** Manages patient records, medications, audit logs, and real-time state.
- **Obsidian (Long-term Memory):** A markdown-based "Clinical Vault" for persistent patient timelines and hospital-wide governance policies.

## 3. Core Workflows

### 3.1 Standard Care Pipeline
A linear orchestration used in the Prescription Console:
1. **Research Agent:** Retrieves patient phenotype and clinical guidelines.
2. **Reasoning Agent:** Analyzes drug-gene interaction risks.
3. **Critic Agent:** Challenges the reasoning for overconfidence or missing data.
4. **Reporter Agent:** Drafts a structured EHR clinical note.
5. **Human Gate:** Final approval required by a clinician.

### 3.2 N-of-1 Research Graph (LangGraph)
A cyclic workflow for iterative therapy optimization:
- **Design → Validate → Revise:** If the **In-Silico Validation Suite** detects biological instability (e.g., high folding energy), it sends revision hints back to the **Design Agent** to optimize the candidate.
- **Deterministic Branching:** The workflow automatically fails if evidence quality is too low, preventing "hallucinated" research.

## 4. Security & Compliance
- **Synthetic Data only:** Zero PII/PHI in the development environment.
- **JWT Authentication:** Role-based access control (RBAC) for all API endpoints.
- **Auditability:** Every agent step, rationale, and confidence score is persisted for clinical review.

---
*GenomicLens Architecture v2.4*
