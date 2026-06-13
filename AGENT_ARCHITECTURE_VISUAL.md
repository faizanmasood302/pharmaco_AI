# Agent Architecture - Visual Flow Diagrams

## 1. High-Level Workflow Architecture

```
+------------------------------------------------------------------------------+
|                        N-of-1 Therapy Generation Pipeline                   |
|                                                                              |
|  INPUT: Patient ID, Target Disease, Max Iterations                         |
|                                                                              |
+------------------------------------------------------------------------------+
|                                                                              |
|                          🛡️ SAFETY GATES LAYER                              |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 1️⃣ REQUEST_GUARDRAILS                                          |         |
|  |    +- Block downstream-use keywords                            |         |
|  |    +- Emit safety warnings                                     |         |
|  |    +- [AUDIT CHECKPOINT [X]]                                     |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|                    🔍 DATA RETRIEVAL LAYER                                   |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 2️⃣ PATIENT_CONTEXT                                             |         |
|  |    +- Fetch patient record                                     |         |
|  |    +- Extract CYP gene profiles                                |         |
|  |    +- [DB Query: ~100-300ms]                                   |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|  +----------------------------------------------------------------+         |
|  | 3️⃣ EVIDENCE_RAG                                                |         |
|  |    +- Query knowledge base (CPIC, PharmGKB)                    |         |
|  |    +- Score evidence quality (high/moderate/low)               |         |
|  |    +- Return sources + rationale                               |         |
|  |    +- [RAG Query: ~200-800ms]                                  |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|              ⚡ DECISION LAYER (With Routing Logic)                          |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 4️⃣ TARGET_SELECTION                                            |         |
|  |    +- Evaluate evidence quality                                |         |
|  |    +- Calculate target confidence                              |         |
|  |    +- IF confidence < 0.4  ---> ❌ FAILURE_REPORT -> END         |         |
|  |    +- ELSE               ---> ✅ Continue to design             |         |
|  |    +- [AUDIT CHECKPOINT [X]]                                     |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|            🔄 GENERATIVE + VALIDATION LOOP (Iterate N Times)                |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 5️⃣ CANDIDATE_DESIGN (Iteration)                                |         |
|  |    +- LLM generates mRNA sequence                              |         |
|  |    +- Apply revision_hints from previous validation            |         |
|  |    +- Store in candidate_history                               |         |
|  |    +- [LLM: ~500-2000ms]                                       |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|  +----------------------------------------------------------------+         |
|  | 6️⃣ VALIDATION (Deterministic)                                  |         |
|  |    +- Critical Checks: RNA alphabet, start/stop codons         |         |
|  |    +- Warning Checks: GC%, homology, immunogenicity            |         |
|  |    +- Calculate overall_risk_score                             |         |
|  |    +- Extract revision_hints for next iteration                |         |
|  |    +- [Deterministic: ~100-200ms]                              |         |
|  |                                                                 |         |
|  |    Decision:                                                   |         |
|  |    +- IF passed ---> Continue to critic                         |         |
|  |    +- IF failed:                                               |         |
|  |       +- IF iteration < max ---> RevisionPlanner (loop)         |         |
|  |       +- ELSE ---> FailureReport (end)                          |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|  +----------------------------------------------------------------+         |
|  | 7️⃣ SAFETY_CRITIC (Human Gate Review)                           |         |
|  |    +- Holistic candidate review                                |         |
|  |    +- Check evidence backing                                   |         |
|  |    +- Identify unresolved risks                                |         |
|  |    +- Emit verdict (research_review_required | revise | failed)|         |
|  |    +- [LLM: ~300-600ms]                                        |         |
|  |    +- [AUDIT CHECKPOINT [X]]                                     |         |
|  |                                                                 |         |
|  |    Routing:                                                    |         |
|  |    +- "research_review_required" ---> Report -> END             |         |
|  |    +- "revise" (iter < max) ---> RevisionPlanner -> LOOP        |         |
|  |    +- "failed" ---> FailureReport -> END                        |         |
|  +----------------------------------------------------------------+         |
|                          v/ (if revise) \v                                    |
|  +----------------------------------------------------------------+         |
|  | 8️⃣ REVISION_PLANNER                                            |         |
|  |    +- Extract hints from validation                            |         |
|  |    +- Prepare for next iteration                               |         |
|  |    +- Jump back to CANDIDATE_DESIGN                            |         |
|  |    +- [~20-50ms]                                               |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|                 📋 REPORTING & HUMAN GATE LAYER                             |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 9️⃣ REPORT (Success Path)                                       |         |
|  |    +- Package final mRNA candidate                             |         |
|  |    +- Generate clinical narrative                              |         |
|  |    +- Flag for human research review                           |         |
|  |    +- Set status = "research_review_required"                 |         |
|  |    +- [AUDIT CHECKPOINT [X]]                                     |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|  +----------------------------------------------------------------+         |
|  | 🚫 FAILURE_REPORT (Failure Path)                               |         |
|  |    +- Document failure reasons                                 |         |
|  |    +- Generate error narrative                                 |         |
|  |    +- Set status = "failed"                                    |         |
|  |    +- [AUDIT CHECKPOINT [X]]                                     |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|                    🔐 HUMAN GATE (Mandatory)                                |
|                                                                              |
|  +----------------------------------------------------------------+         |
|  | 🔑 HUMAN_GATE                                                   |         |
|  |    +- Waiting for clinician/researcher override               |         |
|  |    +- Required fields: reviewer_id, rationale, attestations   |         |
|  |    +- NO autonomous progression beyond this gate               |         |
|  |    +- [Pending external action]                                |         |
|  +----------------------------------------------------------------+         |
|                              v                                               |
|                                                                              |
|  ✅ OUTPUT: TherapyGenerationResponse                                        |
|     +- mrna_sequence: final candidate                                       |
|     +- toxicity_score: risk assessment                                      |
|     +- agent_steps: full execution trace                                    |
|     +- audit_trail: all decisions + rationales                              |
|     +- logic_tree: visualizable decision tree                               |
|     +- human_gate: pending clinician review                                 |
|                                                                              |
+------------------------------------------------------------------------------+
```

---

## 2. Agent Interaction Diagram

```
+---------------------------------------------------------------------------+
|                        AGENT LAYER COMPONENTS                            |
+---------------------------------------------------------------------------+

                      +--------------------------+
                      |   orchestrate_therapy_   |
                      |   generation()           |
                      |   [Entry Point]          |
                      +------------┬-------------+
                                   |
                    +--------------┴--------------+
                    v                             v
        +----------------------+     +----------------------+
        |  research_patient()  |     | retrieve_therapy_    |
        |  [External Agent]    |     | evidence()           |
        |                      |     | [External Agent]     |
        |  Returns:            |     |                      |
        |  - patient dict      |     | Returns:             |
        |  - clinical summary  |     | - evidence bundle    |
        |  - elapsed_ms        |     | - sources            |
        +----------┬-----------+     | - quality level      |
                   |                 +----------┬-----------+
                   |                            |
                   +--------┬-------------------+
                            v
        +--------------------------------------------+
        |  TherapyGraphState (Shared State)          |
        |  -----------------------------------------|
        |  +- patient: {...}                        |
        |  +- patient_context: {...}                |
        |  +- evidence_bundle: {...}                |
        |  +- target_profile: {...}                 |
        |  +- active_candidate: {...}               |
        |  +- candidate_history: [...]              |
        |  +- validation_result: {...}              |
        |  +- critique: {...}                       |
        |  +- iteration: 0-5                        |
        |  +- agent_steps: [AgentStep, ...]         |
        |  +- audit_events: [AuditEvent, ...]       |
        |  +- status: "running" | "..." | "failed"  |
        +--------------------------------------------+
                            v
        +-------------------------------------------------+
        |  THERAPY_GRAPH.invoke(initial_state)           |
        |  ═════════════════════════════════════════════  |
        |                                                  |
        |  ╔═══════════════════════════════════════════╗  |
        |  ║  Nodes:                                   ║  |
        |  ║  1. request_guardrails_node              ║  |
        |  ║  2. patient_context_node                 ║  |
        |  ║  3. evidence_rag_node                    ║  |
        |  ║  4. target_selection_node                ║  |
        |  ║  5. candidate_design_node                ║  |
        |  ║  6. validation_node                      ║  |
        |  ║  7. safety_critic_node                   ║  |
        |  ║  8. revision_planner_node                ║  |
        |  ║  9. report_node                          ║  |
        |  ║  10. failure_report_node                 ║  |
        |  ╚═══════════════════════════════════════════╝  |
        |                                                  |
        |  ╔═══════════════════════════════════════════╗  |
        |  ║  Conditional Edges:                       ║  |
        |  ║  - After target_selection:                ║  |
        |  ║    confidence < 0.4 -> failure_report      ║  |
        |  ║    confidence ≥ 0.4 -> candidate_design    ║  |
        |  ║                                            ║  |
        |  ║  - After safety_critic:                   ║  |
        |  ║    verdict="revise" -> revision_planner    ║  |
        |  ║    verdict="review_required" -> report     ║  |
        |  ║    verdict="failed" -> failure_report      ║  |
        |  ╚═══════════════════════════════════════════╝  |
        +-------------------------------------------------+
                            v
        +--------------------------------------------+
        |  LLM/Generative Services                   |
        |  ----------------------------------------  |
        |  +- design_research_mrna_candidate()       |
        |  |  +- LLM -> mRNA sequence                 |
        |  |  +- ~500-2000ms                         |
        |  |                                          |
        |  +- _reasoning_agent()                     |
        |  |  +- Groq API -> JSON reasoning           |
        |  |  +- Uses fallback deterministic logic   |
        |  |                                          |
        |  +- _critique_agent()                      |
        |     +- Groq API -> structured critique      |
        |     +- Uses fallback deterministic logic   |
        +--------------------------------------------+
                            v
        +--------------------------------------------+
        |  Validation & Scoring                      |
        |  ----------------------------------------  |
        |  +- validate_research_mrna_candidate()     |
        |  |  +- Deterministic checks (RNA alphabet) |
        |  |  +- Bioinformatics simulations          |
        |  |  +- Risk score calculation              |
        |  |  +- ~100-200ms                          |
        |  |                                          |
        |  +- Bioinformatics Adapters:               |
        |     +- simulate_folding_energy()           |
        |     +- simulate_homology_search()          |
        |     +- simulate_immunogenicity_score()     |
        +--------------------------------------------+
                            v
        +--------------------------------------------+
        |  Audit & Observability                     |
        |  ----------------------------------------  |
        |  +- _step(): Create AgentStep              |
        |  +- _audit(): Create AuditEvent           |
        |  +- _append_step(): Add to history         |
        |  +- _append_audit(): Add to trail          |
        +--------------------------------------------+
                            v
        +--------------------------------------------+
        |  orchestrate_therapy_generation()          |
        |  [Return final_state]                      |
        |  ----------------------------------------  |
        |  Returns: TherapyGenerationResponse        |
        |  +- status                                 |
        |  +- mrna_sequence                          |
        |  +- toxicity_score                         |
        |  +- iterations                             |
        |  +- agent_steps                            |
        |  +- audit_trail                            |
        |  +- logic_tree                             |
        |  +- human_gate                             |
        +--------------------------------------------+
```

---

## 3. State Mutation Flow

```
+-------------------------------------------------------------------------+
|                    STATE EVOLUTION DURING EXECUTION                    |
+-------------------------------------------------------------------------+

Initial State (T=0):
╔════════════════════════════════════════════════════════════════╗
║ {                                                              ║
║   therapy_request_id: "uuid-123",                              ║
║   patient_id: "P-001",                                         ║
║   target_disease: "opioid pain response research",             ║
║   max_iterations: 3,                                           ║
║   patient: null,                                               ║
║   patient_context: null,                                       ║
║   evidence_bundle: null,                                       ║
║   target_profile: null,                                        ║
║   candidate_history: [],                                       ║
║   active_candidate: null,                                      ║
║   validation_result: null,                                     ║
║   critique: null,                                              ║
║   revision_hints: [],                                          ║
║   iteration: 0,                                                ║
║   status: "running",                                           ║
║   agent_steps: [],                                             ║
║   audit_events: [],                                            ║
║   safety_notes: []                                             ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                            v [Node: RequestGuardrails]

State After RequestGuardrails (T=50ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   safety_notes: [                                              ║
║     "Research simulation only; not clinically validated.",     ║
║     "No autonomous treatment, dosing, or manufacturing use."   ║
║   ],                                                            ║
║   agent_steps: [AgentStep(agent="RequestGuardrails", ...)],   ║
║   audit_events: [AuditEvent(stage="request_guardrails", ...)] ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: PatientContext, EvidenceRAG]

State After Evidence Retrieval (T=1000ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   patient: {                                                    ║
║     id: "P-001",                                                ║
║     display_name: "John Doe",                                   ║
║     age: 45,                                                    ║
║     sex: "M",                                                   ║
║     indication: "pain management",                              ║
║     cyp_profiles: [                                             ║
║       {gene: "CYP2D6", phenotype: "ultra-rapid metabolizer"}   ║
║     ]                                                           ║
║   },                                                            ║
║   patient_context: {...},                                      ║
║   evidence_bundle: {                                            ║
║     target_rationale: "CYP2D6 ultra-rapid...",                ║
║     evidence_quality: "high",                                   ║
║     sources: ["CPIC_CYP2D6", "PharmGKB"],                      ║
║     known_risks: ["Toxicity in rapid metabolizers"]            ║
║   },                                                            ║
║   target_profile: {                                             ║
║     target_name: "opioid pain response research target",        ║
║     confidence: 0.92,                                           ║
║     evidence_refs: ["CPIC_CYP2D6"]                              ║
║   },                                                            ║
║   agent_steps: [                                                ║
║     AgentStep(agent="RequestGuardrails", ...),                 ║
║     AgentStep(agent="PatientContext", ...),                    ║
║     AgentStep(agent="DiseaseTargetRAG", ...),                  ║
║     AgentStep(agent="TargetSelection", ...)                    ║
║   ],                                                            ║
║   agent_events: [4 audit events logged]                        ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: CandidateDesign - Iter 1]

State After Iteration 1 Design (T=2500ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   iteration: 1,                                                 ║
║   active_candidate: {                                           ║
║     candidate_id: "CAND-2024-001-v1",                          ║
║     sequence: "AUGCUGACUGACUGACUGA...",                        ║
║     rationale: "Designed for ultra-rapid CYP2D6 context...",   ║
║     evidence_refs: ["CPIC_2024"]                                ║
║   },                                                            ║
║   candidate_history: [                                          ║
║     {candidate_id: "CAND-2024-001-v1", ...}                    ║
║   ],                                                            ║
║   agent_steps: [..., AgentStep(agent="CandidateDesign", ...)]  ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: Validation]

State After Validation (T=2700ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   validation_result: {                                          ║
║     passed: false,                                              ║
║     overall_risk_score: 0.68,                                   ║
║     checks: [                                                   ║
║       {name: "rna_alphabet", passed: true, ...},               ║
║       {name: "gc_content", passed: false, severity: "warning"} ║
║     ],                                                          ║
║     blocked_reasons: ["GC content too high"],                  ║
║     revision_hints: [                                           ║
║       "Reduce GC content.",                                     ║
║       "Optimize sequence for higher folding stability."        ║
║     ]                                                           ║
║   },                                                            ║
║   agent_steps: [..., AgentStep(agent="InSilicoValidation", ...)]║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: SafetyCritic]

State After Critic (T=3300ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   critique: {                                                   ║
║     verdict: "revise",                                          ║
║     summary: "Critic requested revision using validation...",   ║
║     unresolved_risks: ["High GC content"],                     ║
║     confidence: 0.75                                            ║
║   },                                                            ║
║   agent_steps: [..., AgentStep(agent="SafetyCritic", ...)]     ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

            v [Routing: verdict="revise" -> RevisionPlanner]

State After RevisionPlanner (T=3350ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   revision_hints: [                                             ║
║     "Reduce GC content.",                                       ║
║     "Optimize sequence for higher folding stability."          ║
║   ],                                                            ║
║   agent_steps: [..., AgentStep(agent="RevisionPlanner", ...)]  ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

            v [Loop Back: CandidateDesign - Iter 2]
            
State After Iteration 2 Design (T=4800ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   iteration: 2,                                                 ║
║   active_candidate: {                                           ║
║     candidate_id: "CAND-2024-001-v2",                          ║
║     sequence: "AUGCUGACUAACUGACUGA...",  [Modified]            ║
║     rationale: "Reduced GC content per feedback...",            ║
║     iteration: 2                                                ║
║   },                                                            ║
║   candidate_history: [                                          ║
║     {candidate_id: "CAND-2024-001-v1", ...},                   ║
║     {candidate_id: "CAND-2024-001-v2", ...}  [NEW]             ║
║   ]                                                             ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: Validation - Iter 2]

State After Validation 2 (T=5000ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   validation_result: {                                          ║
║     passed: true,  [[X] IMPROVED]                                ║
║     overall_risk_score: 0.35,  [v from 0.68]                   ║
║     blocked_reasons: [],  [[X] CLEARED]                          ║
║     revision_hints: []                                          ║
║   }                                                             ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Node: SafetyCritic - Iter 2]

State After Critic 2 (T=5600ms):
╔════════════════════════════════════════════════════════════════╗
║ ... [previous fields] ...                                      ║
║   critique: {                                                   ║
║     verdict: "research_review_required",  [[X] APPROVED]         ║
║     summary: "Critic accepted the candidate for human...",      ║
║     confidence: 0.88                                            ║
║   }                                                             ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝

                    v [Routing: verdict="research_review_required"]

Final State After Report (T=5700ms):
╔════════════════════════════════════════════════════════════════╗
║ {                                                              ║
║   therapy_request_id: "uuid-123",                              ║
║   status: "research_review_required",  [[X] FINAL]              ║
║   patient_id: "P-001",                                         ║
║   target_disease: "opioid pain response research",             ║
║   iterations: 2,                                                ║
║   candidate_history: [v1, v2],                                 ║
║   final_candidate: {id: "CAND-2024-001-v2", ...},              ║
║   clinical_narrative: "Generated CAND-2024-001-v2 as...",      ║
║   agent_steps: [10 steps total],                               ║
║   audit_trail: [10 audit events],                              ║
║   safety_notes: [2 warnings],                                   ║
║   human_gate: {                                                 ║
║     required: true,                                             ║
║     status: "pending",                                          ║
║     required_fields: [                                          ║
║       "reviewer_id",                                            ║
║       "research_rationale",                                     ║
║       "evidence_review_attestation",                            ║
║       "safety_risk_acknowledgement"                             ║
║     ]                                                           ║
║   }                                                             ║
║ }                                                              ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 4. Conditional Routing Decision Tree

```
+------------------------------------------------------------------+
|            WORKFLOW ROUTING DECISION TREE                       |
+------------------------------------------------------------------+

START
  |
  +--> REQUEST_GUARDRAILS
  |    +--> ALWAYS PASS (warnings only)
  |        +--> PATIENT_CONTEXT
  |
  +--> EVIDENCE_RAG
  |
  +--> TARGET_SELECTION
      |
      +--> IF confidence < 0.4 -----------------+
      |                                        |
      |                            FAILURE_REPORT -> END
      |
      +--> IF confidence ≥ 0.4
           |
           +--> CANDIDATE_DESIGN (Iteration=1)
                |
                +--> VALIDATION
                |    |
                |    +--> IF validation.passed = TRUE
                |    |    |
                |    |    +--> SAFETY_CRITIC
                |    |         |
                |    |         +--> IF verdict="research_review_required"
                |    |         |    |
                |    |         |    +--> REPORT -> END
                |    |         |
                |    |         +--> IF verdict="revise" AND iteration < max_iterations
                |    |         |    |
                |    |         |    +--> REVISION_PLANNER
                |    |         |         |
                |    |         |         +--> [LOOP BACK]
                |    |         |             |
                |    |         |             +--> iteration++
                |    |         |                 |
                |    |         |                 +--> CANDIDATE_DESIGN (Iteration=2)
                |    |         |
                |    |         +--> IF verdict="failed"
                |    |              |
                |    |              +--> FAILURE_REPORT -> END
                |    |
                |    +--> IF validation.passed = FALSE
                |         |
                |         +--> IF iteration < max_iterations
                |         |    |
                |         |    +--> REVISION_PLANNER
                |         |         +--> [LOOP BACK]
                |         |
                |         +--> IF iteration ≥ max_iterations
                |              |
                |              +--> SAFETY_CRITIC
                |                  +--> verdict="failed"
                |                      +--> FAILURE_REPORT -> END
                |
                +--> HumanGate (Always) -> Awaiting External Action

═══════════════════════════════════════════════════════════════════

DECISION LOGIC PSEUDOCODE:

  route_after_target_selection(state):
    IF state.target_profile.confidence < 0.4:
      RETURN "failure"
    ELSE:
      RETURN "candidate"

  route_after_critic(state):
    critique = state.critique
    iteration = state.iteration
    max_iter = state.max_iterations
    
    IF critique.verdict == "research_review_required":
      RETURN "report"
    ELIF critique.verdict == "revise" AND iteration < max_iter:
      RETURN "revise"  # -> revision_planner -> candidate_design
    ELSE:
      RETURN "failure"  # -> failure_report
```

---

## 5. Data Flow Between Agents

```
+--------------------------------------------------------------------+
|                    INTER-AGENT DATA FLOW                          |
+--------------------------------------------------------------------+

REQUEST_GUARDRAILS
  |
  +- Reads from state:
  |  +- target_disease
  |
  +- Writes to state:
     +- safety_notes (appended)
     +- agent_steps (appended)
     +- audit_events (appended)

         v

PATIENT_CONTEXT
  |
  +- Calls external: research_patient(patient_id)
  |  +- Returns: (patient_dict, summary, elapsed_ms)
  |
  +- Reads from state:
  |  +- patient_id
  |
  +- Writes to state:
     +- patient ← full patient record
     +- patient_context ← { patient_id, display_name, indication, cyp_profiles, ... }
     +- agent_steps (appended)
     +- audit_events (appended)

         v

EVIDENCE_RAG
  |
  +- Calls external: retrieve_therapy_evidence(target_disease, patient_context)
  |  +- Returns: (evidence_dict, elapsed_ms)
  |
  +- Reads from state:
  |  +- target_disease
  |  +- patient_context
  |
  +- Writes to state:
     +- evidence_bundle ← { target_rationale, evidence_quality, sources, known_risks, ... }
     +- agent_steps (appended)
     +- audit_events (appended)

         v

TARGET_SELECTION
  |
  +- Reads from state:
  |  +- evidence_bundle (quality, sources)
  |  +- target_disease
  |  +- patient_context
  |
  +- Writes to state:
     +- target_profile ← { target_name, target_type, confidence, evidence_refs, rationale, ... }
     +- agent_steps (appended)
     +- audit_events (appended)

         v [Conditional Routing]
         |
         +--> If confidence < 0.4 -> FAILURE_REPORT
         |
         +--> If confidence ≥ 0.4 -> CANDIDATE_DESIGN

             v

CANDIDATE_DESIGN
  |
  +- Calls external: design_research_mrna_candidate(
  |                    patient, target_disease, 
  |                    evidence_bundle, iteration, 
  |                    revision_hints)
  |  +- Returns: (candidate_dict, elapsed_ms)
  |
  +- Reads from state:
  |  +- patient
  |  +- target_disease
  |  +- evidence_bundle
  |  +- iteration
  |  +- revision_hints (from previous validation)
  |  +- candidate_history
  |
  +- Writes to state:
     +- iteration ← iteration + 1
     +- active_candidate ← new candidate
     +- candidate_history.append(active_candidate)
     +- revision_hints ← [] (reset)
     +- agent_steps (appended)
     +- audit_events (appended)

         v

VALIDATION
  |
  +- Calls external: validate_research_mrna_candidate(sequence)
  |  +- Returns: (validation_dict, elapsed_ms)
  |
  +- Reads from state:
  |  +- active_candidate.sequence
  |
  +- Writes to state:
     +- validation_result ← { passed, overall_risk_score, checks, blocked_reasons, revision_hints, ... }
     +- agent_steps (appended)
     +- audit_events (appended)

         v [Validation Decision]
         |
         +--> If passed -> SAFETY_CRITIC
         |
         +--> If failed:
             +--> If iteration < max -> REVISION_PLANNER
             +--> If iteration ≥ max -> SAFETY_CRITIC (verdict=failed)

             v

SAFETY_CRITIC
  |
  +- Calls external: _critique_agent(reasoning, patient, medication, ...) [Optional LLM]
  |  +- Returns: critique_dict
  |
  +- Reads from state:
  |  +- evidence_bundle (sources, known_risks)
  |  +- validation_result (passed status)
  |  +- iteration
  |  +- max_iterations
  |  +- active_candidate
  |
  +- Writes to state:
     +- critique ← { verdict, summary, unresolved_risks, required_review_fields, confidence, ... }
     +- agent_steps (appended)
     +- audit_events (appended)

         v [Routing Decision]
         |
         +--> If verdict="research_review_required" -> REPORT
         |
         +--> If verdict="revise" (iter < max) -> REVISION_PLANNER
         |
         +--> If verdict="failed" -> FAILURE_REPORT

             v [Optional: REVISION_PLANNER]
             |
             +- Reads from state:
             |  +- validation_result.revision_hints
             |
             +- Writes to state:
                +- revision_hints ← extracted hints
                +- agent_steps (appended)
                +- audit_events (appended)
                    |
                    +--> [LOOP BACK to CANDIDATE_DESIGN]

             v

REPORT or FAILURE_REPORT
  |
  +- Reads from state:
  |  +- active_candidate
  |  +- evidence_bundle
  |  +- validation_result
  |  +- iteration
  |  +- target_disease
  |  +- critique (if applicable)
  |
  +- Writes to state:
     +- status ← "research_review_required" | "failed"
     +- clinical_narrative ← generated narrative
     +- agent_steps (appended)
     +- audit_events (appended)

         v

FINAL OUTPUT: TherapyGenerationResponse
  |
  +- Aggregates:
  |  +- status, mrna_sequence, toxicity_score, iterations
  |  +- agent_steps (full trace)
  |  +- audit_trail (all decisions)
  |  +- logic_tree (decision visualization)
  |  +- safety_notes
  |  +- human_gate (mandatory review)
  |
  +--> Returned to API layer
```

---

## 6. Confidence Score Propagation

```
+------------------------------------------------------------------+
|          CONFIDENCE SCORE TRACKING THROUGH WORKFLOW              |
+------------------------------------------------------------------+

Evidence Quality -> Target Confidence
------------------------------------
  "high"       -> confidence = 0.92
  "moderate"   -> confidence = 0.78
  "low"        -> confidence = 0.25
  no sources   -> confidence = 0.15

  Decision: IF confidence < 0.4 -> BLOCK


Validation Risk Score Composition
----------------------------------
  baseline                    = 0.10
  + critical failures (×0.12) = X
  + repeat_risk (×0.15)       = Y
  + immunogenicity (×0.20)    = Z
  + gc_deviation (≤0.25)      = W
  ---------------------------------
  overall_risk_score          = min(1.0, sum)

  Decision: IF overall ≤ 0.50 -> PASS
            IF overall > 0.50 -> FAIL


Agent Step Confidence (Execution Trace)
---------------------------------------
  RequestGuardrails    -> 1.0 (deterministic)
  PatientContext       -> 0.95 (DB query reliability)
  DiseaseTargetRAG     -> 0.9 (evidence search)
  TargetSelection      -> 0.92 (evidence-based)
  CandidateDesign      -> 0.82 (LLM-generated)
  InSilicoValidation   -> 0.9 (deterministic + sim)
  SafetyCritic         -> 0.75-0.88 (LLM-based)
  Reporter             -> 0.88 (template generation)
  HumanGate            -> 1.0 (requires human)


Final Decision Confidence
-------------------------
  decision_confidence = avg(
    reasoning.decision_confidence,
    critique.challenge_confidence
  )

  Example:
    Reasoning confidence = 0.85
    Critique confidence  = 0.92
    -----------------------------
    Final confidence     = 0.88


Low Confidence Triggers
-----------------------
  IF target_profile.confidence < 0.4
    -> BLOCK at target_selection
    -> Route to failure_report

  IF validation_result.overall_risk_score > 0.50 AND iteration < max
    -> Request revision
    -> Route to revision_planner

  IF evidence_quality = "low" OR no sources
    -> Audit event with requires_human_review=True
    -> Safety critic may still proceed but with caution
```

---

## 7. Error Handling & Fallback Paths

```
+------------------------------------------------------------------+
|              ERROR HANDLING & FALLBACK LOGIC                    |
+------------------------------------------------------------------+

ERROR: Evidence retrieval returns empty sources
------------------------------------------------
  1. EvidenceRAG
     +- evidence_sources = []
        evidence_quality = "low"

  2. TargetSelection
     +- confidence = 0.15 (below 0.4 threshold)
        status = "blocked"

  3. Route Decision
     +- confidence < 0.4 -> FAILURE_REPORT

  4. Output
     +- status = "failed"
        clinical_narrative = "No source-backed evidence retrieved"


ERROR: Patient not found in database
--------------------------------------
  1. PatientContext
     +- research_patient() returns None or empty dict

  2. State Updated
     +- patient = None or {}
        patient_context = {} (defaults)

  3. Downstream Impact
     +- CandidateDesign still proceeds
        +- LLM generates with limited context

  4. Output
     +- status = "research_review_required" (if validation passes)
        clinical_narrative = "Generated candidate with limited patient data"


ERROR: LLM call fails (Groq API down)
--------------------------------------
  1. CandidateDesign
     +- design_research_mrna_candidate() returns fallback

  2. SafetyCritic
     +- _critique_agent() fails
        +- Use _fallback_critique()

  3. _fallback_critique()
     +- Uses deterministic logic based on reasoning output
        +- Maps risk_level to verdict (logic preserved)

  4. Output
     +- status = "research_review_required" (deterministic route)
        audit_trail = [(..., "LLM fallback used")]


ERROR: Validation always fails (max iterations exceeded)
---------------------------------------------------------
  1. Iteration 1: validation fails
     -> RevisionPlanner extracts hints
     -> Loop back to CandidateDesign

  2. Iteration 2: validation fails
     -> RevisionPlanner extracts hints
     -> Loop back to CandidateDesign

  3. Iteration 3: validation fails
     -> iteration (3) ≥ max_iterations (3)
     -> SafetyCritic verdict = "failed"

  4. Route Decision
     +- verdict != "research_review_required"
        -> FAILURE_REPORT

  5. Output
     +- status = "failed"
        iterations = 3
        clinical_narrative = "Failed after 3 iterations"


ERROR: Bioinformatics simulation hangs
---------------------------------------
  1. validate_research_mrna_candidate()
     +- simulate_folding_energy() timeout

  2. Fallback
     +- Return default risk score (0.5)
     +- Mark check as "warning" not "critical"

  3. Validation Result
     +- overall_risk_score = 0.50 (threshold)
        passed = false (on boundary)

  4. SafetyCritic Decision
     +- Depends on other factors
        +- May still route to research_review if evidence is strong


ERROR: State mutation conflicts
--------------------------------
  (Not applicable in LangGraph - uses immutable pattern)

  Each node:
    old_state -> pure function -> new_state (no mutation)
  Graph orchestrator merges states atomically
```

