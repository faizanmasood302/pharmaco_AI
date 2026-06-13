# Agent Layer Architecture - Pharmacogenomic Harness

## System Overview

The Agent Layer is built on **LangGraph** (an agentic state machine framework) and implements a multi-stage therapeutic candidate generation workflow with deterministic validation gates and human oversight checkpoints.

```
+---------------------------------------------------------------------+
|                    Agent Orchestration Layer                        |
|                   (Therapy Generation Pipeline)                     |
+---------------------------------------------------------------------+
|                                                                     |
|  INPUT: (patient_id, target_disease, max_iterations)              |
|    v                                                               |
|  +-----------------------------------------------------------+    |
|  |  THERAPY_GRAPH (LangGraph StateGraph)                     |    |
|  |  ------------------------------------------------------- |    |
|  |                                                            |    |
|  |  1. REQUEST_GUARDRAILS ---> Safety policy check           |    |
|  |     v                                                      |    |
|  |  2. PATIENT_CONTEXT -------> Load patient phenotypes      |    |
|  |     v                                                      |    |
|  |  3. EVIDENCE_RAG ----------> Retrieve clinical evidence   |    |
|  |     v                                                      |    |
|  |  4. TARGET_SELECTION ------> Choose therapeutic target    |    |
|  |     v                                                      |    |
|  |     [Conditional: Block if confidence < 0.4]             |    |
|  |     +- FAILURE_REPORT ---> END                            |    |
|  |     +- CANDIDATE_DESIGN                                   |    |
|  |        v                                                   |    |
|  |  5. CANDIDATE_DESIGN ------> Generate mRNA sequence       |    |
|  |     (Iterates based on feedback)                          |    |
|  |     v                                                      |    |
|  |  6. VALIDATION -------------> In-silico safety checks     |    |
|  |     v                                                      |    |
|  |  7. SAFETY_CRITIC ----------> Review & critique result    |    |
|  |     v                                                      |    |
|  |     [Conditional Routing]                                 |    |
|  |     +- "research_review_required" ---> REPORT             |    |
|  |     +- "revise" -------------------> REVISION_PLANNER     |    |
|  |     +- "failed" -----------------> FAILURE_REPORT         |    |
|  |        v                                                   |    |
|  |  8. REVISION_PLANNER -------> Extract hints for retry     |    |
|  |     v                                                      |    |
|  |     [Loop back to CANDIDATE_DESIGN if iterations remain] |    |
|  |                                                            |    |
|  |  9. REPORT -----------------> Package final result        |    |
|  |     v                                                      |    |
|  |  10. FAILURE_REPORT ---------> Document failure reasons   |    |
|  |     v                                                      |    |
|  |  OUTPUT: TherapyGenerationResponse                       |    |
|  |  +- final_candidate (mRNA sequence)                      |    |
|  |  +- validation_result (risk scores)                      |    |
|  |  +- evidence_bundle (source references)                  |    |
|  |  +- agent_steps (execution trace)                        |    |
|  |  +- audit_trail (decision log)                           |    |
|  |  +- logic_tree (decision visualization)                  |    |
|  |  +- human_gate (pending clinician review)                |    |
|  +-----------------------------------------------------------+    |
|                                                                     |
+---------------------------------------------------------------------+
```

---

## State Graph Definition

### TherapyGraphState (Shared State Dictionary)

```python
TherapyGraphState = {
    # Request Context
    therapy_request_id: str           # UUID for tracking
    patient_id: str                   # Patient identifier
    target_disease: str               # Disease/indication
    max_iterations: int               # Retry limit (1-5)
    
    # Data Artifacts
    patient: dict[str, Any]           # Full patient record
    patient_context: dict[str, Any]   # Extracted context
    evidence_bundle: dict[str, Any]   # Evidence retrieval result
    target_profile: dict[str, Any]    # Selected target metadata
    
    # Candidate History
    candidate_history: list[dict]     # All generated candidates
    active_candidate: dict[str, Any]  # Current candidate
    validation_result: dict[str, Any] # Current validation output
    critique: dict[str, Any]          # Critic's assessment
    revision_hints: list[str]         # Hints for next iteration
    
    # Workflow Tracking
    iteration: int                    # Current iteration counter
    status: str                       # "running" | "research_review_required" | "failed"
    agent_steps: list[AgentStep]      # Execution trace
    audit_events: list[AuditEvent]    # Audit trail
    safety_notes: list[str]           # Safety warnings
    clinical_narrative: str           # Summary for human review
}
```

---

## Agent Nodes (Detailed Breakdown)

### 1. REQUEST_GUARDRAILS_NODE
**Purpose**: Enforce safety policy constraints at request boundary

**Responsibilities**:
- Check if request contains downstream-use keywords ("dose", "inject", "manufacturing-ready")
- Add safety warnings to the response
- Log audit checkpoint (human=True)

**Output State Updates**:
```python
{
    "target_disease": "opioid pain response research",
    "safety_notes": [
        "Research simulation only; not clinically validated.",
        "No autonomous treatment, dosing, or manufacturing use."
    ],
    "agent_steps": [...],
    "audit_events": [...]
}
```

**Decision Logic**: None - always passes forward (warnings only)

---

### 2. PATIENT_CONTEXT_NODE
**Purpose**: Hydrate patient phenotype and clinical context

**Calls**: `research_patient(patient_id)` -> returns (patient_dict, summary, elapsed_ms)

**Extracted Data**:
```python
patient_context = {
    "patient_id": "P-001",
    "display_name": "John Doe",
    "indication": "pain management",
    "cyp_profiles": [
        {"gene": "CYP2D6", "phenotype": "ultra-rapid metabolizer"}
    ],
    "clinical_history_summary": "...",
    "safety_constraints": [
        "Use patient phenotype as context only.",
        "Do not infer dosing or treatment authorization."
    ]
}
```

**Output State Updates**:
- `patient` ← full record
- `patient_context` ← extracted dict
- `agent_steps.append(AgentStep(...))`
- `audit_events.append(AuditEvent(...))`

**Decision Logic**: None - always succeeds

---

### 3. EVIDENCE_RAG_NODE
**Purpose**: Retrieve evidence for target disease + patient context

**Calls**: `retrieve_therapy_evidence(target_disease, patient_context)` 
-> returns (evidence_dict, elapsed_ms)

**Evidence Bundle Structure**:
```python
evidence = {
    "target_rationale": "CYP2D6 ultra-rapid phenotype increases...",
    "evidence_quality": "high" | "moderate" | "low",
    "sources": ["CPIC_CYP2D6_Codeine", "PharmGKB_CYP2D6_Opioid"],
    "known_risks": ["Toxicity risk", "Treatment failure"],
    "target_type": "gene_pathway" | "protein_target"
}
```

**Confidence Mapping**:
- high -> 0.9
- moderate -> 0.74
- low -> 0.35

**Decision Logic**: 
- If `evidence["sources"]` is empty -> status = "blocked"
- If evidence_quality != "high" -> audit requires human review
- Otherwise -> status = "complete"

---

### 4. TARGET_SELECTION_NODE
**Purpose**: Decide on therapeutic target based on evidence quality

**Logic Flow**:
```
IF not evidence.sources OR evidence_quality == "low"
  THEN status = "blocked"
       confidence = 0.15-0.25
       rationale = "Insufficient research evidence"
ELSE
  status = "complete"
  confidence = 0.78-0.92 (based on evidence_quality)
  target_profile = {
    "target_name": f"{target_disease} research target",
    "target_type": "pathway" if "pathway" in rationale else "protein",
    "evidence_refs": sources,
    "confidence": confidence
  }
```

**Routing Decision** (_route_after_target_selection):
```python
IF target_profile.confidence < 0.4
  THEN route = "failure_report"  # Block workflow
ELSE
  route = "candidate_design"      # Proceed to design phase
```

**Output State Updates**:
- `target_profile` ← decision data
- `agent_steps.append(...)`
- `audit_events.append(AuditEvent(stage="target_selection", ...))`

---

### 5. CANDIDATE_DESIGN_NODE
**Purpose**: Generate mRNA candidate sequence iteratively

**Calls**: `design_research_mrna_candidate(patient, target_disease, evidence_bundle, iteration, revision_hints)`
-> returns (candidate_dict, elapsed_ms)

**Candidate Structure**:
```python
candidate = {
    "candidate_id": "CAND-2024-001-v1",
    "sequence": "AUGCUGACUGACUGAC...",  # mRNA sequence
    "rationale": "Optimized for CYP2D6 ultra-rapid metabolizer...",
    "evidence_refs": ["CPIC_2024"],
    "iteration": 1,
    "design_parameters": {
        "codon_optimization": "human",
        "gc_content": 0.52,
        "start_codon": "AUG",
        "stop_codon": "UAA"
    }
}
```

**Iteration Loop**:
1. First iteration: No revision hints -> generate baseline
2. Subsequent iterations: Use `revision_hints` from validation to refine
3. Stop when: Pass validation OR reach max_iterations

**Output State Updates**:
- `iteration` ← incremented
- `active_candidate` ← new candidate
- `candidate_history.append(candidate)` ← track all
- `revision_hints` ← reset to []
- `agent_steps.append(...)`
- `audit_events.append(...)`

---

### 6. VALIDATION_NODE
**Purpose**: Run deterministic in-silico checks on mRNA sequence

**Calls**: `validate_research_mrna_candidate(sequence)` 
-> returns (validation_dict, elapsed_ms)

**Validation Checks** (from validation.py):
```
Critical Checks (Must Pass):
  [X] rna_alphabet: Only A, U, G, C
  [X] reading_frame: Length ≥ 30, divisible by 3
  [X] start_codon: Begins with AUG
  [X] terminal_stop: Ends with UAA/UAG/UGA
  [X] internal_stop_codons: None in coding region

Warning Checks (Contribute to Score):
  [WARNING] folding_stability: MFE ≤ -25.0 kcal/mol
  [WARNING] homology_off_target: No high-identity matches
  [WARNING] immunogenicity_risk: Score ≤ 0.4
  [WARNING] gc_content: 0.35 ≤ GC% ≤ 0.70
  [WARNING] repeat_motif_risk: Codon repeat ratio ≤ 0.30
```

**Risk Score Calculation**:
```python
failure_weight = sum(0.12 for check if not passed)
risk_score = min(1.0, 
    0.10                              # baseline
    + failure_weight                  # critical failures
    + (repeat_risk * 0.15)            # motif penalties
    + (immunogenicity * 0.20)         # immunogenicity weight
    + min(abs(gc - 0.52), 0.25)       # GC content deviation
)
```

**Pass Criteria**:
- `passed = (not blocked_reasons) AND (risk_score ≤ 0.50)`

**Output**:
```python
validation_result = {
    "passed": True | False,
    "overall_risk_score": 0.35,
    "checks": [
        {
            "name": "rna_alphabet",
            "passed": True,
            "score": 1.0,
            "detail": "Sequence uses only A, U, G, and C.",
            "severity": "critical"
        },
        ...
    ],
    "blocked_reasons": ["Internal stop codons detected"],
    "revision_hints": [
        "Remove internal stop codons from coding region",
        "Optimize sequence for higher folding stability (lower MFE)"
    ],
    "validator_version": "1.4.2-research"
}
```

**Decision Logic**: 
- If validation passes -> proceed to safety_critic
- If validation fails AND iterations < max -> route to revision_planner
- If validation fails AND iterations ≥ max -> route to failure_report

---

### 7. SAFETY_CRITIC_NODE
**Purpose**: Review candidate holistically; gate for human research review

**Logic Flow**:
```python
unresolved_risks = evidence.known_risks

IF not evidence.sources:
  verdict = "failed"
  summary = "No source-backed evidence retrieved"
  
ELIF not validation.passed:
  IF iteration < max_iterations:
    verdict = "revise"
    summary = "Critic requested revision using validation feedback"
  ELSE:
    verdict = "failed"
    summary = "Maximum validation attempts exceeded"
    
ELSE:  # Validation passed
  verdict = "research_review_required"
  summary = "Critic accepted candidate for human-gated research review"
```

**Critique Output**:
```python
critique = {
    "verdict": "research_review_required" | "revise" | "failed",
    "summary": "...",
    "unresolved_risks": ["Toxicity in ultra-rapid", "..."],
    "required_review_fields": [
        "reviewer_id",
        "research_rationale",
        "evidence_review_attestation",
        "safety_risk_acknowledgement"
    ],
    "confidence": 0.86
}
```

**Routing Decision** (_route_after_critic):
```python
IF verdict == "research_review_required"
  THEN route = "report"         # Package for human gate
ELIF verdict == "revise" AND iteration < max_iterations
  THEN route = "revise"         # Loop back to revision_planner
ELSE
  route = "failure"              # End with failure
```

---

### 8. REVISION_PLANNER_NODE
**Purpose**: Extract and structure hints for next iteration

**Logic**:
```python
hints = validation.revision_hints OR ["Revise candidate using critic feedback"]
```

**Output State Updates**:
- `revision_hints` ← hints (used by next CANDIDATE_DESIGN call)
- `agent_steps.append(...)`
- `audit_events.append(AuditEvent(stage="revision_planning", decision="retry", ...))`

**Then Loops Back**: -> CANDIDATE_DESIGN (with incremented iteration)

---

### 9. REPORT_NODE
**Purpose**: Package successful candidate for human research review

**Narrative Generation**:
```python
narrative = (
    f"Generated {candidate_id} as simulated n-of-1 mRNA research candidate "
    f"for {target_disease}. Validation risk score: {risk_score}. "
    f"Evidence sources: {sources}. Human research review required."
)
```

**Output State Updates**:
- `status` ← "research_review_required"
- `clinical_narrative` ← narrative
- Routes to END (exit point)

---

### 10. FAILURE_REPORT_NODE
**Purpose**: Document why workflow ended in failure

**Failure Reasons** (Priority Order):
1. Validation blocked_reasons (if any)
2. Target profile low confidence
3. Unresolved critic risks
4. Default: "Did not meet research simulation safety requirements"

**Narrative**:
```python
narrative = (
    f"N-of-1 research simulation failed for {target_disease}. "
    f"Reason: {'; '.join(reasons)}. "
    f"Human review required before retrying."
)
```

**Output State Updates**:
- `status` ← "failed"
- `clinical_narrative` ← narrative
- Routes to END (exit point)

---

## Routing Graph (Edges & Transitions)

```
START
  v
guardrails -----------> patient_context
  v                        v
  |                   evidence_rag
  |                        v
  |                  target_selection
  |                     v/  (conditional)  \v
  |              candidate            failure_report -> END
  |              design v
  |              validation v
  |              safety_critic
  |                  v/ (conditional) \v
  |            report v/  revise ^\  failure_report -> END
  |            v                v
  |            END        revision_planner -> [back to candidate_design]
```

---

## Input & Output Contracts

### Input: `orchestrate_therapy_generation(patient_id, target_disease, max_iterations)`

```python
def orchestrate_therapy_generation(
    patient_id: str,                    # "P-001"
    target_disease: str,                # "opioid pain response research"
    max_iterations: int = 3,            # Retries for validation feedback
) -> TherapyGenerationResponse:
```

### Output: `TherapyGenerationResponse`

```python
TherapyGenerationResponse = {
    # Status & Metadata
    "status": "research_review_required" | "failed",
    "therapy_request_id": "uuid-string",
    "patient_id": "P-001",
    "target_disease": "opioid pain response research",
    "iterations": 3,
    
    # Results
    "mrna_sequence": "AUGCUGACUGAC...",
    "toxicity_score": 0.35,
    "candidate_id": "CAND-2024-001-v3",
    
    # Decision Artifacts
    "final_candidate": TherapyCandidate(...),
    "candidate_history": [TherapyCandidate(...), ...],
    "validation_result": TherapyValidationResult(...),
    "evidence_bundle": TherapyEvidenceBundle(...),
    
    # Audit & Observability
    "agent_steps": [AgentStep(...), ...],           # Execution trace
    "audit_trail": [AuditEvent(...), ...],          # Decision log
    "logic_tree": {...},                            # Visualization
    "safety_notes": ["Research simulation only", ...],
    
    # Human Review Gating
    "human_gate": HumanGate(
        required=True,
        status="pending",
        reason="Researcher or clinician review required",
        required_fields=[
            "reviewer_id",
            "research_rationale",
            "evidence_review_attestation",
            "safety_risk_acknowledgement"
        ]
    ),
    
    # Documentation
    "clinical_narrative": "Generated CAND-2024-001-v3 as n-of-1 mRNA..."
}
```

---

## Data Flow Diagram

```
+-----------------+
|   Patient ID    |
| Target Disease  |
|  Max Iterations |
+--------┬--------+
         v
    +------------------------------------------+
    | REQUEST_GUARDRAILS                       |
    | +- Safety policy check                   |
    | +- Log audit checkpoint                  |
    +------┬-----------------------------------+
           v (safety_notes added)
    +------------------------------------------+
    | PATIENT_CONTEXT                          |
    | +- Fetch patient from DB                 |
    | +- Extract CYP profiles                  |
    | +- Create patient_context dict           |
    +------┬-----------------------------------+
           v (patient, patient_context added)
    +------------------------------------------+
    | EVIDENCE_RAG                             |
    | +- Query knowledge base                  |
    | +- Rank by relevance                     |
    | +- Score evidence quality                |
    | +- Return sources + rationale            |
    +------┬-----------------------------------+
           v (evidence_bundle added)
    +------------------------------------------+
    | TARGET_SELECTION                         |
    | +- Evaluate evidence quality             |
    | +- Check confidence threshold            |
    | +- Create target_profile                 |
    +------┬-----------------------------------+
           v (target_profile added)
      [Conditional Router]
      +- Confidence < 0.4 -> FAILURE_REPORT -> END
      +- Confidence ≥ 0.4 -> CANDIDATE_DESIGN
                              v
    +------------------------------------------+
    | CANDIDATE_DESIGN (Iteration Loop)        |
    | +- LLM generates mRNA sequence           |
    | +- Apply revision_hints (if any)         |
    | +- Create candidate dict                 |
    | +- Add to candidate_history              |
    +------┬-----------------------------------+
           v (active_candidate added, iteration++)
    +------------------------------------------+
    | VALIDATION                               |
    | +- Deterministic checks on sequence      |
    | +- Calculate risk_score                  |
    | +- Extract revision_hints                |
    | +- Return validation_result              |
    +------┬-----------------------------------+
           v (validation_result added)
    +------------------------------------------+
    | SAFETY_CRITIC                            |
    | +- Review candidate holistically         |
    | +- Check evidence backing                |
    | +- Assess unresolved risks               |
    | +- Emit verdict                          |
    +------┬-----------------------------------+
           v (critique added)
      [Conditional Router]
      +- verdict="research_review_required" -> REPORT -> END
      +- verdict="revise" (iter < max) -> REVISION_PLANNER -> CANDIDATE_DESIGN
      +- verdict="failed" -> FAILURE_REPORT -> END
                              v
    +------------------------------------------+
    | REPORT or FAILURE_REPORT                 |
    | +- Generate clinical_narrative           |
    | +- Set final status                      |
    | +- Create human_gate object              |
    +------┬-----------------------------------+
           v
    +-----------------------------------------+
    | TherapyGenerationResponse                |
    | +- mrna_sequence                         |
    | +- toxicity_score                        |
    | +- agent_steps (full trace)              |
    | +- audit_trail (decisions)               |
    | +- human_gate (pending review)           |
    +-----------------------------------------+
```

---

## Audit Trail Checkpoints

Every decision gate records an `AuditEvent`:

```python
AuditEvent = {
    "stage": "request_guardrails",      # Node identifier
    "decision": "pass" | "block" | "review_required" | "retry" | "failed",
    "rationale": "Request constrained to research simulation only...",
    "requires_human_review": True
}
```

**Checkpoints**:
1. **request_guardrails** -> human=True (all requests logged)
2. **patient_context** -> human=False
3. **evidence_retrieval** -> human=quality != "high"
4. **target_selection** -> human=True
5. **candidate_design** -> human=True
6. **in_silico_validation** -> human=True
7. **safety_critic** -> human=True
8. **revision_planning** -> human=True
9. **human_gate** -> human=True

**Total Coverage**: Every significant workflow decision has an audit record.

---

## Agent Step Tracking

Each node appends an `AgentStep`:

```python
AgentStep = {
    "agent": "CandidateDesign",                    # Node name
    "status": "complete" | "blocked" | "approved" | "review_required",
    "summary": "Iteration 1: Designed mRNA for CYP2D6...",
    "duration_ms": 1234,                           # Execution time
    "confidence": 0.82,                            # Certainty score
    "evidence_refs": ["CPIC_2024", "PharmGKB"]    # Source citations
}
```

**Full Agent Steps Sequence**:
1. RequestGuardrails
2. PatientContext
3. DiseaseTargetRAG
4. TargetSelection
5. CandidateDesign (x N iterations)
6. InSilicoValidation
7. SafetyCritic
8. RevisionPlanner (if retry)
9. Reporter or FailureReport
10. HumanGate

---

## Iteration & Feedback Loop

```
ITERATION 1:
  +- CandidateDesign -> "baseline mRNA"
  +- Validation -> blocked_reasons: ["GC content too high", "Off-target homology"]
  |               revision_hints: ["Reduce GC content", "Modify homology regions"]
  +- SafetyCritic -> verdict = "revise"
  +- RevisionPlanner -> Extract hints for next iteration

ITERATION 2:
  +- CandidateDesign (with hints) -> "refined mRNA v2"
  +- Validation -> risk_score: 0.45 (improved from 0.68)
  |               blocked_reasons: [] (all critical passed!)
  |               revision_hints: [] (clean)
  +- SafetyCritic -> verdict = "research_review_required"
  +- REPORT -> Package for human review

FINAL OUTPUT:
  {
    "status": "research_review_required",
    "iterations": 2,
    "final_candidate": {...},
    "candidate_history": [v1, v2],
    "agent_steps": [full trace],
    "audit_trail": [all decisions],
    "human_gate": {"required": True, "status": "pending"}
  }
```

---

## Error Handling & Fallbacks

**If Evidence Retrieval Fails**:
- `evidence_sources = []`
- SafetyCritic verdict = "failed"
- Narrative: "No source-backed evidence was retrieved"

**If Validation Loops Max Iterations**:
- Exit after iteration == max_iterations
- SafetyCritic verdict = "failed"
- Log "Maximum validation attempts exceeded"

**If Patient Not Found**:
- `patient = None`
- PatientContext still proceeds (creates empty dict)
- Downstream processes work with defaults

**If Evidence Quality Too Low**:
- `confidence = 0.35` (low threshold)
- TargetSelection -> blocks (confidence < 0.4)
- Routes to FAILURE_REPORT

---

## Key Design Patterns

### 1. **State as Single Source of Truth**
- All nodes read from + write to shared `TherapyGraphState`
- No side effects or external state mutations
- Full auditability: entire state history preserved

### 2. **Deterministic Validation + LLM Reasoning**
- Validation layer uses deterministic checks (reproducible)
- Generative layer uses LLMs (creative but non-deterministic)
- Combined approach: creativity + safety

### 3. **Human Gate at Entry & Exit**
- **Entry**: RequestGuardrails blocks downstream terms
- **Exit**: HumanGate forces clinician review before use
- **Checkpoints**: Every decision logged for audit trail

### 4. **Feedback Loop with Iteration Limit**
- Candidate fails validation -> extract hints
- Regenerate with hints -> validate again
- Max 5 iterations (configurable) to prevent infinite loops

### 5. **Confidence Scoring**
- Evidence quality -> confidence (high=0.9, moderate=0.74, low=0.35)
- Target selection blocks if confidence < 0.4
- Each agent step reports confidence (0.0-1.0)
- Final response includes decision_confidence

---

## Performance Characteristics

| Node | Time (ms) | Bottleneck | Caching? |
|------|-----------|-----------|----------|
| RequestGuardrails | 10-50 | Regex check | No |
| PatientContext | 100-300 | DB query | Yes (patient table) |
| EvidenceRAG | 200-800 | Vector search | Yes (RAG cache) |
| TargetSelection | 50-100 | Logic | No |
| CandidateDesign | 500-2000 | LLM call | No |
| Validation | 100-200 | Bioinformatics sims | No |
| SafetyCritic | 300-600 | LLM call | No |
| RevisionPlanner | 20-50 | Logic | No |
| Report/FailureReport | 50-100 | Narrative gen | No |

**Total Workflow**: 1.5-5 seconds (depends on iterations + LLM latency)

---

## Security & Compliance

✅ **HIPAA Audit Trail**: Every decision logged with timestamp, user_id, patient_id
✅ **Human Override Required**: No autonomous clinical decision
✅ **Evidence Grounding**: All recommendations cite sources
✅ **Safety Gates**: Multiple rejection points (confidence, evidence, validation)
✅ **Risk Scoring**: Transparent numerical justification
✅ **Revocation Path**: Failed candidates documented for review

---

## Integration with API Layer

```
POST /api/generate-therapy
{
  "patient_id": "P-001",
  "target_disease": "opioid pain response research",
  "max_iterations": 3
}
  v
orchestrate_therapy_generation() [Agent Layer]
  v
THERAPY_GRAPH.invoke(initial_state)
  v
Response: TherapyGenerationResponse
  v
save_therapy_generation(patient_id, response)  [DB]
  v
200 OK + JSON response
```

---

## Monitoring & Observability

**Logged Metrics**:
- `agent_steps[*].duration_ms` -> latency per node
- `agent_steps[*].confidence` -> certainty per decision
- `iteration` -> how many retries needed
- `overall_risk_score` -> final safety assessment
- `audit_trail[*]` -> decision log for compliance

**Example Observability Query**:
```sql
SELECT patient_id, status, iterations, 
       (SELECT AVG(confidence) FROM audit_trail) as avg_confidence,
       DATEDIFF(max(timestamp), min(timestamp)) as total_duration_ms
FROM therapy_generations
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY patient_id
```

