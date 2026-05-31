## 1. Project Background, System Directive & Architecture Overview

**System Directive for AI CLI:**
Act as a Senior AI Architect and Full-Stack Developer. Your explicit goal is to scaffold a production-ready MVP for a high-growth medical tech startup. The codebase must be highly modular, strongly typed, and optimized for a split frontend/backend stack (Next.js + Python). Prioritize strict, clean API contracts between the web client and the multi-agent backend. Do not hallucinate features outside of this document.

**The Clinical Problem (The "Why"):**
Modern medicine suffers from a dual crisis caused by generalized, "one-size-fits-all" prescribing. Standard drug dosages lead to a $1.45 trillion substance abuse crisis (when genetically vulnerable patients experience massive euphoric spikes from prodrugs like Codeine) and a $290 billion medication non-adherence crisis (when drugs are ineffective or cause severe side effects due to poor metabolization). 

**The Pharmacogenomic Solution (The "What"):**
This project is an AI "agent harness" designed to intercept and prevent these dangerous prescriptions. By leveraging n-of-1 genetic data (specifically Cytochrome P450 enzyme phenotypes), the system shifts care from reactive to predictive. To bypass the 12-to-18-month enterprise hospital sales cycle, this MVP is deliberately architected to ingest synthetic FHIR-formatted data, positioning the product for immediate deployment in agile, independent boutique pain management clinics and Direct-to-Consumer (DTC) telehealth platforms.

**Core Technical Mechanism & Data Flow (The "How"):**
* **Phase 1: Input & Trigger:** A clinician utilizes the Next.js web interface to submit a proposed treatment plan, sending a JSON payload containing a synthetic `patient_id` and `proposed_medication` to the Python FastAPI backend.
* **Phase 2: Multi-Agent Orchestration:** A Python multi-agent pipeline (powered by Groq for near-instant inference) takes over the request. 
    * The **Orchestrator Agent** acts as the router for the workflow.
    * The **Research Agent** queries a Supabase PostgreSQL database to extract the patient's specific metabolic phenotype.
    * The **Analyst Agent** cross-references the proposed drug's pharmacokinetic pathways against the patient's genetic profile to calculate conversion risk.
    * The **Critic Agent** evaluates that risk. If a severe mismatch is found (e.g., prescribing an opioid prodrug to an "Ultra-Rapid Metabolizer"), it flags the prescription and calculates a biologically safe alternative.
* **Phase 3: Visual Informatics Output:** The backend returns a strictly formatted JSON evaluation. The Next.js frontend receives this payload. If the prescription is flagged, the UI triggers an immersive 3D warning using React Three Fiber and GSAP—animating a dark-mode biotech visualization (like a pulsing wireframe liver) to immediately alert the clinician and display the safe alternative.