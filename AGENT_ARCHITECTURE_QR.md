# Agent Architecture - Quick Reference

## 10-Node Workflow at a Glance

```
1️⃣  RequestGuardrails  -> Enforce safety policy
2️⃣  PatientContext     -> Load patient phenotype
3️⃣  EvidenceRAG        -> Retrieve clinical evidence
4️⃣  TargetSelection    -> Choose therapeutic target [CONDITIONAL GATE]
    +- confidence < 0.4 -> FAILURE_REPORT -> END
    +- confidence ≥ 0.4 -> CANDIDATE_DESIGN
5️⃣  CandidateDesign    -> Generate mRNA sequence (Iteration Loop)
6️⃣  Validation         -> Run in-silico checks
    +- PASS -> SAFETY_CRITIC
    +- FAIL -> {if iter < max: REVISION_PLANNER (LOOP), else: SAFETY_CRITIC}
7️⃣  SafetyCritic       -> Holistic review [CONDITIONAL GATE]
    +- "research_review_required" -> REPORT -> END
    +- "revise" (iter < max) -> REVISION_PLANNER -> {LOOP to CANDIDATE_DESIGN}
    +- "failed" -> FAILURE_REPORT -> END
8️⃣  RevisionPlanner    -> Extract hints for retry
9️⃣  Report             -> Package for human review (SUCCESS PATH)
🚫  FailureReport      -> Document failure reasons (FAILURE PATH)
🔑  HumanGate          -> Mandatory clinician override (ALWAYS)
```

---

## State Mutations Per Node

| Node | Reads | Writes |
|------|-------|--------|
| RequestGuardrails | target_disease | safety_notes, agent_steps, audit_events |
| PatientContext | patient_id | patient, patient_context, agent_steps, audit_events |
| EvidenceRAG | target_disease, patient_context | evidence_bundle, agent_steps, audit_events |
| TargetSelection | evidence_bundle, target_disease | target_profile, agent_steps, audit_events |
| CandidateDesign | patient, target_disease, evidence_bundle, iteration, revision_hints | iteration++, active_candidate, candidate_history, revision_hints=[], agent_steps, audit_events |
| Validation | active_candidate.sequence | validation_result, agent_steps, audit_events |
| SafetyCritic | evidence_bundle, validation_result, iteration, max_iterations | critique, agent_steps, audit_events |
| RevisionPlanner | validation_result | revision_hints, agent_steps, audit_events |
| Report | active_candidate, evidence_bundle, validation_result, target_disease | status, clinical_narrative, agent_steps, audit_events |
| FailureReport | validation_result, target_profile, critique | status, clinical_narrative, agent_steps, audit_events |

---

## Key Decision Gates

### 1. TARGET_SELECTION Gate
```python
IF evidence.sources is EMPTY OR evidence_quality == "low"
  confidence = 0.15-0.35 (below threshold)
  ROUTE = "failure_report"
ELSE
  confidence = 0.78-0.92 (above threshold)
  ROUTE = "candidate_design"
```

### 2. VALIDATION Check
```python
IF validation.passed == TRUE
  ROUTE = "safety_critic"
ELSE IF iteration < max_iterations
  ROUTE = "revision_planner"
ELSE
  ROUTE = "safety_critic" (will fail there)
```

### 3. SAFETY_CRITIC Gate
```python
IF verdict == "research_review_required"
  ROUTE = "report"
ELSE IF verdict == "revise" AND iteration < max_iterations
  ROUTE = "revision_planner" (LOOP BACK)
ELSE
  ROUTE = "failure_report"
```

---

## Confidence Score Mapping

**Evidence Quality -> Target Confidence**
- `high` -> 0.92 (proceed)
- `moderate` -> 0.78 (proceed)
- `low` -> 0.25 (block if < 0.4)
- no sources -> 0.15 (block)

**Validation Risk Score**
```
risk = 0.10 (baseline)
     + (failures × 0.12)
     + (repeat_risk × 0.15)
     + (immunogenicity × 0.20)
     + min(|gc - 0.52|, 0.25)
```
- Pass: risk ≤ 0.50
- Fail: risk > 0.50

---

## Iteration Loop Example

```
ITERATION 1:
  CandidateDesign(hints=[])
    -> mRNA v1
  Validation
    -> FAIL (risk=0.68, GC too high)
    -> revision_hints=["Reduce GC", "Optimize folding"]
  SafetyCritic
    -> verdict="revise"
  RevisionPlanner
    -> revision_hints set
  ---------------------------------
  LOOP BACK to CandidateDesign

ITERATION 2:
  CandidateDesign(hints=["Reduce GC", "Optimize folding"])
    -> mRNA v2 (improved)
  Validation
    -> PASS (risk=0.35)
  SafetyCritic
    -> verdict="research_review_required"
  Report
    -> Package for human review
  ---------------------------------
  EXIT to HumanGate (pending)
```

---

## API Integration

### Request
```json
POST /api/generate-therapy
{
  "patient_id": "P-001",
  "target_disease": "opioid pain response research",
  "max_iterations": 3
}
```

### Response (Success)
```json
{
  "status": "research_review_required",
  "mrna_sequence": "AUGCUGACUGAC...",
  "toxicity_score": 0.35,
  "iterations": 2,
  "candidate_id": "CAND-2024-001-v2",
  "agent_steps": [
    {
      "agent": "RequestGuardrails",
      "status": "complete",
      "confidence": 1.0,
      "duration_ms": 45
    },
    ...
  ],
  "audit_trail": [
    {
      "stage": "request_guardrails",
      "decision": "pass",
      "rationale": "...",
      "requires_human_review": true
    },
    ...
  ],
  "logic_tree": {
    "node": "N-of-1 Research Simulation",
    "children": [...]
  },
  "human_gate": {
    "required": true,
    "status": "pending",
    "required_fields": [
      "reviewer_id",
      "research_rationale",
      "evidence_review_attestation",
      "safety_risk_acknowledgement"
    ]
  }
}
```

### Response (Failure)
```json
{
  "status": "failed",
  "iterations": 1,
  "clinical_narrative": "Failed: Insufficient evidence quality",
  "agent_steps": [...],
  "audit_trail": [...],
  "human_gate": {...}
}
```

---

## Performance Profile

| Node | Latency | Bottleneck |
|------|---------|-----------|
| RequestGuardrails | 10-50ms | Regex |
| PatientContext | 100-300ms | DB query |
| EvidenceRAG | 200-800ms | Vector search |
| TargetSelection | 50-100ms | Logic |
| CandidateDesign | 500-2000ms | LLM |
| Validation | 100-200ms | Simulation |
| SafetyCritic | 300-600ms | LLM |
| RevisionPlanner | 20-50ms | Logic |
| Report/Failure | 50-100ms | Template |
| **TOTAL (1 iter)** | **1.5-5s** | LLM calls |
| **TOTAL (3 iters)** | **3-15s** | Retry loops |

---

## Audit Trail Checkpoints

[X] **Mandatory Logging Points** (10 checkpoints):
1. RequestGuardrails - Safety policy enforcement
2. PatientContext - Patient data loaded
3. EvidenceRetrieval - Evidence sources ranked
4. TargetSelection - Target confidence assessed
5. CandidateDesign - mRNA generated (per iteration)
6. InSilicoValidation - Validation passed/failed
7. SafetyCritic - Verdict issued
8. RevisionPlanning - Retry hints extracted (if applicable)
9. HumanGate - Awaiting clinician override
10. Reporter/Failure - Final decision documented

Each checkpoint includes:
- stage (node name)
- decision (pass/block/review_required/retry/failed)
- rationale (human-readable)
- requires_human_review (boolean)
- timestamp

---

## External Dependencies

| Service | Used In | Fallback |
|---------|---------|----------|
| Groq API (LLM) | CandidateDesign, SafetyCritic | Deterministic logic |
| Supabase (DB) | PatientContext, Auth, Audit | Error -> return auth_failed |
| RAG Vector DB | EvidenceRAG | Empty results -> low confidence |
| Bioinformatics Sim | Validation | Default risk scores |

---

## Error Handling Strategy

**All errors gracefully degrade**:
- LLM timeouts -> Use deterministic fallback
- DB unavailable -> Return auth error (safe fail)
- Missing patient -> Proceed with defaults
- Bad evidence -> Low confidence -> Block at TargetSelection
- Max iterations reached -> Exit loop, route to critic for failure verdict

---

## Safety Guarantees

✅ **No autonomous clinical use**
- Human gate always required
- Cannot bypass clinician review
- All recommendations backed by evidence

✅ **Full auditability**
- Every decision logged with rationale
- Immutable audit trail
- Request correlation IDs for tracing

✅ **Deterministic validation**
- Sequence checks reproducible
- Risk scoring transparent
- No randomness in critical gates (only warnings)

✅ **Evidence grounding**
- All recommendations cite sources
- Quality ranking visible
- No claims without backing

---

## Monitoring Essentials

**Key Metrics to Track**:
- Latency per node (p95, p99)
- Success rate (research_review_required + successes)
- Failure rate + reasons
- Iteration count distribution
- Human override rate
- Evidence quality distribution

**Key Dashboards**:
- Real-time workflow status
- Agent performance
- External service health
- Audit & compliance

**Key Alerts**:
- Latency > 30s
- Error rate > 10%
- LLM API down
- DB connection issues

---

## Deployment Checklist

- [ ] LangGraph installed
- [ ] Groq API key configured
- [ ] Supabase connection pooling set up
- [ ] RAG vector DB indexed
- [ ] Bioinformatics adapters deployed
- [ ] Request correlation ID middleware
- [ ] Structured logging configured
- [ ] Rate limiter initialized (per user)
- [ ] Health check endpoint
- [ ] Graceful shutdown handlers
- [ ] Monitoring & alerting connected
- [ ] Audit table schema created
- [ ] User authentication tested
- [ ] Load testing (concurrent requests)

---

## Quick Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Always fails at TargetSelection | Evidence quality too low | Check RAG index / knowledge base |
| Infinite loop | Max iterations not enforced | Verify iteration counter logic |
| LLM fallback triggered repeatedly | Groq API rate limit | Implement request queue / backoff |
| Validation always passes/fails | Risk score threshold wrong | Review validation thresholds |
| Slow PatientContext | DB query slow | Check patient table index |
| Slow EvidenceRAG | Vector search slow | Optimize embeddings / cache |
| Missing audit events | Logging misconfigured | Check audit table permissions |
| Human gate never unlocked | Override endpoint not called | Verify API integration with frontend |

---

## Files Generated

1. **AGENT_ARCHITECTURE.md** - 400+ lines
   - Full node-by-node breakdown
   - State management details
   - Data flow documentation
   - Audit trail patterns

2. **AGENT_ARCHITECTURE_VISUAL.md** - 500+ lines
   - ASCII workflow diagrams
   - Agent interaction diagrams
   - State mutation examples
   - Routing decision trees
   - Confidence propagation
   - Error handling paths

3. **AGENT_LAYER_INTEGRATION.md** - 350+ lines
   - End-to-end request flow
   - Component interaction matrix
   - Deployment architecture
   - Monitoring setup
   - Security & compliance checklist

4. **AGENT_ARCHITECTURE_QR.md** (this file)
   - Quick reference
   - At-a-glance summary
   - Decision tree reference
   - Performance profile
   - Troubleshooting guide

---

## Next Steps

1. **Review** the architecture files with your team
2. **Validate** design assumptions against your requirements
3. **Customize** thresholds (confidence < 0.4, risk ≤ 0.50, max_iterations = 3)
4. **Test** with sample patients in dev environment
5. **Monitor** key metrics in production
6. **Iterate** based on real-world performance data
