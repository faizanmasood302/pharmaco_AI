# Agent Layer Integration - Full System Architecture

## End-to-End Request Flow (Frontend -> Backend -> Agent -> Frontend)

```
+------------------------------------------------------------------------------+
|                           USER & FRONTEND LAYER                             |
|                          (Next.js + TypeScript)                             |
+------------------------------------------------------------------------------+
|                                                                              |
|  User: Fills TherapySimulationPanel form                                    |
|  +- Target Disease: "opioid pain response research"                        |
|  +- Patient ID: "P-001"                                                     |
|  +- Max Iterations: 3                                                       |
|  +- Clicks "Run Simulation"                                                |
|                                                                              |
|         v handleSubmit() -> fetch() [with BetterAuth token]                 |
|                                                                              |
|  POST /api/generate-therapy HTTP/1.1                                       |
|  {                                                                           |
|    "patient_id": "P-001",                                                   |
|    "target_disease": "opioid pain response research",                       |
|    "max_iterations": 3                                                      |
|  }                                                                           |
|                                                                              |
+------------------------------------------------------------------------------+
                                    v
+------------------------------------------------------------------------------+
|                      FASTAPI BACKEND PERIMETER                              |
|                    (agent-server/main.py, auth.py)                          |
+------------------------------------------------------------------------------+
|                                                                              |
|  POST /api/generate-therapy
|  +- Extract Authorization: Bearer <token>                                   |
|  |  +- Call verify_token(credentials) [auth.py]                           |
|  |     +- Query Supabase session table                                     |
|  |     +- Return user_id (or raise AuthFailedError)                        |
|  |                                                                          |
|  +- Parse request body -> TherapyGenerationRequest                          |
|  |  +- {patient_id, target_disease, max_iterations}                        |
|  |                                                                          |
|  +- log_audit(user_id, "therapy_generation_started", patient_id)          |
|  |  +- Insert audit_logs record to Supabase                               |
|  |                                                                          |
|  +- Rate limit check (per user_id)                                         |
|  |  +- limiter.limit("100/minute")(user_id)                               |
|  |  +- Return 429 if exceeded                                              |
|  |                                                                          |
|  +- Forward to agent orchestration                                          |
|                                                                              |
+------------------------------------------------------------------------------+
                                    v
+------------------------------------------------------------------------------+
|                        AGENT LAYER ORCHESTRATION                            |
|                  (agents/therapy_orchestrator.py)                           |
|                                                                              |
|  +--------------------------------------------------------------------+    |
|  | orchestrate_therapy_generation(                                   |    |
|  |   patient_id="P-001",                                            |    |
|  |   target_disease="opioid pain response research",                |    |
|  |   max_iterations=3                                               |    |
|  | )                                                                |    |
|  +--------------------------------------------------------------------+    |
|                              v                                               |
|  ╔════════════════════════════════════════════════════════════════╗         |
|  ║  THERAPY_GRAPH.invoke(initial_state) [LangGraph]               ║         |
|  ║                                                                 ║         |
|  ║  1. REQUEST_GUARDRAILS                                         ║         |
|  ║  2. PATIENT_CONTEXT -> research_patient()                       ║         |
|  ║  3. EVIDENCE_RAG -> retrieve_therapy_evidence()                 ║         |
|  ║  4. TARGET_SELECTION (with conditional routing)                ║         |
|  ║  5-7. CANDIDATE_DESIGN -> VALIDATION -> SAFETY_CRITIC            ║         |
|  ║     (loop with REVISION_PLANNER if needed)                     ║         |
|  ║  8-9. REPORT or FAILURE_REPORT                                 ║         |
|  ║                                                                 ║         |
|  ║  🔍 Full execution trace in agent_steps[]                      ║         |
|  ║  📋 Audit trail in audit_events[]                              ║         |
|  ║  📊 Decision tree in logic_tree{}                              ║         |
|  ║                                                                 ║         |
|  ║  Duration: ~1.5-5 seconds (depending on LLM latency)           ║         |
|  ╚════════════════════════════════════════════════════════════════╝         |
|                              v                                               |
|  +--------------------------------------------------------------------+    |
|  | TherapyGenerationResponse                                         |    |
|  | {                                                                  |    |
|  |   "status": "research_review_required",                           |    |
|  |   "mrna_sequence": "AUGCUGACUGAC...",                             |    |
|  |   "toxicity_score": 0.35,                                         |    |
|  |   "iterations": 2,                                                |    |
|  |   "candidate_id": "CAND-2024-001-v2",                             |    |
|  |   "agent_steps": [AgentStep(...), ...],  # Full trace            |    |
|  |   "audit_trail": [AuditEvent(...), ...], # Decisions             |    |
|  |   "logic_tree": {...},                   # Visualization         |    |
|  |   "human_gate": {                                                 |    |
|  |     "required": true,                                             |    |
|  |     "status": "pending",                                          |    |
|  |     "required_fields": [...]                                      |    |
|  |   }                                                               |    |
|  | }                                                                 |    |
|  +--------------------------------------------------------------------+    |
|                              v                                               |
|  save_therapy_generation(                                                   |
|    patient_id="P-001",                                                      |
|    response=TherapyGenerationResponse(...),                                 |
|    user_id=<verified_user_id>                                               |
|  )                                                                           |
|  +- INSERT into therapy_generations table                                  |
|     +- id, patient_id, request_json, status, created_at, ...               |
|     +- Return: generation_id (UUID)                                        |
|                                                                              |
+------------------------------------------------------------------------------+
                                    v
+------------------------------------------------------------------------------+
|                        FASTAPI RESPONSE                                     |
|                                                                              |
|  HTTP 200 OK                                                                |
|  Content-Type: application/json                                             |
|  X-Request-ID: uuid-correlation-id                                          |
|  {                                                                           |
|    "status": "research_review_required",                                    |
|    "mrna_sequence": "...",                                                  |
|    "toxicity_score": 0.35,                                                  |
|    "iterations": 2,                                                         |
|    "candidate_id": "CAND-2024-001-v2",                                      |
|    "agent_steps": [...],                                                    |
|    "audit_trail": [...],                                                    |
|    "logic_tree": {...},                                                     |
|    "human_gate": {...}                                                      |
|  }                                                                           |
|                                                                              |
+------------------------------------------------------------------------------+
                                    v
+------------------------------------------------------------------------------+
|                      FRONTEND RENDERING                                     |
|                                                                              |
|  TherapySimulationPanel
|  +- setResult(response)
|  +- Render "Research Review Required" status
|  +- Display logic_tree as interactive visualization
|  +- Show mRNA sequence (copyable)
|  +- Display agent_steps[] as timeline
|  +- Show audit_trail[] for compliance
|  +- Highlight human_gate requirements
|  +- Disable automated progression (human gate locked)
|
|  User reviews and submits override decision:
|  +- Reviewer ID: <clinical user>
|  +- Research Rationale: "..."
|  +- Evidence Review Attestation: [X]
|  +- Safety Risk Acknowledgement: [X]
|  +- Clicks "Approve for Research"
|                                                                              |
+------------------------------------------------------------------------------+
```

---

## Component Interaction Matrix

```
+-----------------------------------------------------------------------------+
|                    COMPONENT INTERACTION MATRIX                            |
|                                                                             |
|  How Agent Layer Interacts with Other Layers                               |
+-----------------------------------------------------------------------------+

FRONTEND LAYER
--------------
  [X] Receives TherapyGenerationResponse from API
  [X] Displays agent_steps[] as execution timeline
  [X] Shows logic_tree{} as decision visualization
  [X] Renders audit_trail[] for compliance audit
  [X] Enforces human_gate (no auto-progression)
  [X] Sends override decision back to API (if approved)
  ✗ Does NOT call agent layer directly

API LAYER (FastAPI)
-------------------
  [X] Receives request from frontend
  [X] Authenticates user via verify_token()
  [X] Logs audit event: therapy_generation_started
  [X] Calls orchestrate_therapy_generation() [AGENT LAYER]
  [X] Receives TherapyGenerationResponse
  [X] Calls save_therapy_generation() [DB LAYER]
  [X] Returns response to frontend
  [X] Rate limits per user
  ✗ Does NOT bypass authentication for agent calls

AGENT LAYER (LangGraph)
-----------------------
  [X] Orchestrates THERAPY_GRAPH workflow
  [X] Calls external agents:
  |  +- research_patient() [pulls from DB via service]
  |  +- retrieve_therapy_evidence() [RAG service]
  |  +- design_research_mrna_candidate() [LLM service]
  |  +- validate_research_mrna_candidate() [deterministic validator]
  |  +- Groq API calls [for LLM reasoning/critique]
  [X] Tracks full execution in agent_steps[]
  [X] Records all decisions in audit_events[]
  [X] Builds decision tree in logic_tree{}
  [X] Sets human_gate for mandatory human review
  ✗ Does NOT persist results directly (API layer handles persistence)

DB LAYER (Supabase)
-------------------
  [X] CALLED BY API LAYER:
  |  +- get_admin_client() [for auth verification]
  |  +- verify session against session table
  |  +- insert audit_logs
  |  +- save_therapy_generation()
  |  +- update_therapy_decision() [after human review]
  [X] CALLED BY AGENT LAYER INDIRECTLY:
  |  +- research_patient() queries patients table
  |  +- retrieve_therapy_evidence() may query knowledge tables
  |  +- validate_therapy_decision() queries therapy_generations
  ✗ Direct agent-to-DB queries go through service layer

EXTERNAL SERVICES
------------------
  [X] Groq API
  |  +- Used in: design_research_mrna_candidate()
  |  +- Used in: _reasoning_agent()
  |  +- Used in: _critique_agent()
  |  +- Fallback: Deterministic logic if API fails
  [X] Bioinformatics Simulator
  |  +- Used in: validate_research_mrna_candidate()
  |  +- simulate_folding_energy()
  |  +- simulate_homology_search()
  |  +- simulate_immunogenicity_score()
  [X] Vector DB / RAG Index
  |  +- Used in: retrieve_therapy_evidence() [similarity search]

═══════════════════════════════════════════════════════════════════════════════

DATA FLOW DIRECTIONS:

  Frontend
    v
  API (auth, rate limit)
    v
  Agent Layer (orchestration)
    +--> External Services (Groq, Bioinformatics)
    +--> Service Layer (research_patient, retrieve_evidence)
        +--> DB (queries only, no writes from agent)
    v
  API (persistence)
    +--> DB (save_therapy_generation)
    +--> Frontend (response)
```

---

## Deployment & Scalability Architecture

```
+------------------------------------------------------------------------------+
|                    DEPLOYMENT ARCHITECTURE                                 |
+------------------------------------------------------------------------------+

+-----------------------------------------------------------------+
| FRONTEND (Next.js)                                              |
| +- Deployment: Vercel / Self-hosted                            |
| +- Environment: Node.js runtime                                |
| +- Connection: HTTPS to API Gateway                            |
+-----------------------------------------------------------------+
                          v (HTTPS)
+-----------------------------------------------------------------+
| API GATEWAY (AWS ALB / CloudFlare)                              |
| +- Load balancing                                               |
| +- SSL/TLS termination                                          |
| +- Rate limiting (before reaching backend)                     |
| +- CORS headers                                                 |
+-----------------------------------------------------------------+
                          v
+------------------------------------------------------------------+
| BACKEND CLUSTER (FastAPI + Agent Layer)                          |
|                                                                  |
| +------------------+ +------------------+ +------------------+  |
| |  Instance 1      | |  Instance 2      | |  Instance N      |  |
| |  +------------+  | |  +------------+  | |  +------------+  |  |
| |  | FastAPI   |  | |  | FastAPI   |  | |  | FastAPI   |  |  |
| |  | + Agent   |  | |  | + Agent   |  | |  | + Agent   |  |  |
| |  | Layer     |  | |  | Layer     |  | |  | Layer     |  |  |
| |  +------------+  | |  +------------+  | |  +------------+  |  |
| |  CPU: 2-4 cores | |  CPU: 2-4 cores | |  CPU: 2-4 cores |  |
| |  Mem: 4-8 GB    | |  Mem: 4-8 GB    | |  Mem: 4-8 GB    |  |
| |  Timeout: 30s   | |  Timeout: 30s   | |  Timeout: 30s   |  |
| +------------------+ +------------------+ +------------------+  |
|                                                                  |
| Health Check: /healthz (every 10s)                             |
| Graceful Shutdown: 30s SIGTERM wait                            |
| Auto-scaling: CPU > 70% -> scale up                             |
+------------------------------------------------------------------+
                v                    v
        +---------------------------------------+
        | EXTERNAL SERVICES                     |
        +---------------------------------------+
        | Groq API (LLM)                        |
        | +- Rate limit: 100 req/min (default) |
        |                                       |
        | Supabase (DB + Auth)                  |
        | +- Connection pooling: 20 conns       |
        |                                       |
        | RAG Vector DB (Knowledge)             |
        | +- Cached embeddings                  |
        |                                       |
        | Monitoring (Grafana + Prometheus)     |
        | +- Agent execution traces             |
        +---------------------------------------+


PERFORMANCE CHARACTERISTICS:

  Latency Budget (Per Request):
    +- Auth + Rate limit:    50-100 ms
    +- RequestGuardrails:    10-50 ms
    +- PatientContext (DB):  100-300 ms
    +- EvidenceRAG (search): 200-800 ms
    +- TargetSelection:      50-100 ms
    +- CandidateDesign (LLM): 500-2000 ms
    +- Validation:           100-200 ms
    +- SafetyCritic (LLM):   300-600 ms
    +- [Iteration Loop]      (if retry)
    ------------------------
    TOTAL:                   1.5-5 seconds (single iteration)
                             3-15 seconds (3 iterations)

  Concurrency:
    +- Max concurrent requests: N instances × 1 (per instance limit)
    +- Reason: Groq API rate limiting (100 req/min shared)
    +- Mitigation: Queue requests / async processing later
    +- Current model: Synchronous + blocking per request


RESOURCE UTILIZATION:

  Per Request:
    +- CPU: 1-2 cores (depends on LLM latency waiting)
    +- Memory: 200-500 MB (state + LLM tokenization)
    +- Network: ~5-10 MB (API calls + DB queries)
    +- Duration: 1.5-5 seconds

  Cost Model (AWS):
    +- Compute: $0.05-0.15 per request
    +- LLM (Groq): $0.02-0.10 per request
    +- DB (Supabase): $0.002-0.01 per request
    +- Storage: ~100 KB per generation (audit trail)
    +- TOTAL: ~$0.10-0.30 per generation
```

---

## Agent Layer Dependencies & Imports

```python
# DEPENDENCIES MAP

+-----------------------------------------------------------------+
|  Agent Layer (agents/therapy_orchestrator.py)                  |
+-----------------------------------------------------------------+

from langgraph.graph import END, START, StateGraph
    +- LangGraph framework for state machine orchestration

from agents.generative import design_research_mrna_candidate
    +- LLM-based mRNA candidate generation

from agents.research import research_patient
    +- Patient profile retrieval + context extraction

from agents.therapy_rag import retrieve_therapy_evidence
    +- Evidence retrieval from knowledge base

from agents.validation import validate_research_mrna_candidate
    +- Deterministic in-silico validation checks

from agents.bioinformatics_adapter import (
    simulate_folding_energy,
    simulate_homology_search,
    simulate_immunogenicity_score
)
    +- Mocked bioinformatics simulations

from models import (
    AgentStep, AuditEvent, HumanGate,
    TherapyCandidate, TherapyEvidenceBundle,
    TherapyGenerationResponse, TherapyValidationResult
)
    +- Pydantic models for type safety


+-----------------------------------------------------------------+
|  External Agent Services                                        |
+-----------------------------------------------------------------+

agents.research.research_patient()
    |
    +--> db.supabase.get_admin_client()
        +--> supabase.table("patients").select(...)

agents.therapy_rag.retrieve_therapy_evidence()
    |
    +--> Vector DB / RAG index search
    +--> Cache layer for frequent queries

agents.generative.design_research_mrna_candidate()
    |
    +--> LLM provider (Groq / Claude)
    +--> Prompt engineering
    +--> Output parsing + validation

agents.validation.validate_research_mrna_candidate()
    |
    +--> Deterministic checks (no external deps)
    +--> agents.bioinformatics_adapter (simulations)


+-----------------------------------------------------------------+
|  Integration with API Layer                                    |
+-----------------------------------------------------------------+

main.py: POST /api/generate-therapy
    |
    +--> verify_token() [auth.py]
    +--> log_audit() [audit.py]
    +--> orchestrate_therapy_generation() [AGENT LAYER]
    +--> save_therapy_generation() [db/supabase.py]
    +--> return response
```

---

## Monitoring & Observability

```
+------------------------------------------------------------------------------+
|                   MONITORING & OBSERVABILITY STACK                          |
+------------------------------------------------------------------------------+

METRICS (Prometheus)
--------------------
  therapy_generation_duration_seconds
    +- By status: "research_review_required", "failed"
    +- By iteration count: 1, 2, 3, 4, 5
    +- Histogram: [0-1s, 1-2s, 2-5s, 5-10s, >10s]

  agent_step_duration_ms
    +- Per node: RequestGuardrails, PatientContext, ...
    +- With success/failure tags
    +- Percentile tracking: p50, p95, p99

  agent_step_confidence_score
    +- Per node type
    +- Distribution histogram

  evidence_quality_distribution
    +- "high", "moderate", "low"
    +- Counts and trends

  validation_risk_score_distribution
    +- Histogram of overall_risk_score
    +- Pass rate percentage

  human_gate_decision_rate
    +- Approved vs Rejected
    +- Time to decision

  therapy_generation_iteration_count
    +- Single iteration vs Multi-iteration
    +- Retry rate

  error_rate_by_node
    +- Node name
    +- Error type (LLM timeout, DB error, etc.)
    +- Recovery attempts


LOGS (Structured)
-----------------
  Log format: JSON with correlation ID

  {
    "timestamp": "2024-06-06T10:30:45Z",
    "request_id": "uuid-correlation-id",
    "user_id": "user-123",
    "patient_id": "P-001",
    "level": "INFO",
    "message": "Starting therapy generation workflow",
    "context": {
      "target_disease": "opioid pain response research",
      "max_iterations": 3
    }
  }

  Trace points:
    +- [INFO] therapy_generation_started
    +- [INFO] patient_context_retrieved
    +- [INFO] evidence_retrieved
    +- [INFO] target_selected (confidence: 0.92)
    +- [INFO] candidate_generated (iteration: 1)
    +- [INFO] validation_passed | validation_failed
    +- [INFO] critic_verdict: research_review_required
    +- [ERROR] LLM_API_TIMEOUT (fallback used)
    +- [INFO] therapy_generation_completed (status: research_review_required)


TRACES (Distributed)
--------------------
  Jaeger / OpenTelemetry integration

  Span hierarchy:
    orchestrate_therapy_generation [root]
    +- request_guardrails_node
    +- patient_context_node
    |  +- research_patient() [external]
    +- evidence_rag_node
    |  +- retrieve_therapy_evidence() [external]
    +- target_selection_node
    +- candidate_design_node
    |  +- design_research_mrna_candidate() [external, LLM call]
    |  +- Retry logic if timeout
    +- validation_node
    |  +- validate_research_mrna_candidate()
    |  +- simulate_folding_energy()
    |  +- simulate_homology_search()
    |  +- simulate_immunogenicity_score()
    +- safety_critic_node
    |  +- _critique_agent() [external, LLM call]
    +- [LOOP back if revision needed]
    +- report_node or failure_report_node


DASHBOARDS (Grafana)
--------------------
  Dashboard 1: Real-time Workflow Status
    +- Requests in flight (by status)
    +- Average latency per node
    +- Success rate (research_review_required + success)
    +- Failure rate (by reason)
    +- P95 / P99 latencies

  Dashboard 2: Agent Performance
    +- Evidence retrieval quality distribution
    +- Target confidence scores (histogram)
    +- Validation pass rate by iteration
    +- Retry loop frequency
    +- Human override rate

  Dashboard 3: External Service Health
    +- Groq API availability
    +- Groq API latency
    +- Supabase query performance
    +- RAG retrieval latency
    +- Circuit breaker status

  Dashboard 4: Audit & Compliance
    +- Audit events logged per hour
    +- Human gate decisions (by reviewer)
    +- Decision time (from generation to approval)
    +- Regulatory violations (if any)


ALERTING (PagerDuty)
--------------------
  CRITICAL:
    +- Agent latency > 30s
    +- Error rate > 10%
    +- Groq API down (fallback engaged)
    +- DB connection pool exhausted

  WARNING:
    +- Agent latency > 10s (p95)
    +- Error rate > 5%
    +- High LLM retry rate (>20%)
    +- Cache hit rate < 50%
```

---

## Security & Compliance Integration

```
+------------------------------------------------------------------------------+
|              SECURITY & COMPLIANCE IN AGENT LAYER                           |
+------------------------------------------------------------------------------+

AUTHENTICATION & AUTHORIZATION
-------------------------------
  [X] Every API call to /api/generate-therapy requires:
    +- BetterAuth session token (HTTPBearer)
    +- Valid session in Supabase
    +- Non-expired token
    +- User ID extraction from session

  [X] Agent layer runs within authenticated context:
    +- user_id from verify_token() passed to agents
    +- All audit logs include user_id
    +- Cannot impersonate other users


AUDIT TRAIL & COMPLIANCE
------------------------
  [X] Every workflow generates audit_events[]:
    
    Each AuditEvent contains:
      +- stage: "request_guardrails", "target_selection", ...
      +- decision: "pass", "block", "review_required", ...
      +- rationale: Human-readable decision reason
      +- requires_human_review: Boolean flag

  [X] Full decision trace:
    
    [RequestGuardrails] -> pass
      +- rationale: "Request constrained to research simulation"
      +- requires_human_review: true
      +- timestamp: 2024-06-06T10:30:45Z

    [EvidenceRetrieval] -> pass
      +- rationale: "Retrieved 2 high-quality sources"
      +- requires_human_review: false
      +- timestamp: 2024-06-06T10:30:46Z

    [TargetSelection] -> pass
      +- rationale: "Evidence quality HIGH, confidence 0.92"
      +- requires_human_review: true
      +- timestamp: 2024-06-06T10:30:47Z

    ... (full trace) ...

    [HumanGate] -> pending
      +- rationale: "Clinician approval required before release"
      +- requires_human_review: true
      +- timestamp: 2024-06-06T10:30:52Z


HUMAN GATE (Mandatory Override)
-------------------------------
  [X] No autonomous clinical use:
    +- status always = "research_review_required" | "failed"

  [X] Human gate structure:
    {
      "required": true,
      "status": "pending",
      "reason": "Researcher or clinician review required before use",
      "required_fields": [
        "reviewer_id",
        "research_rationale",
        "evidence_review_attestation",
        "safety_risk_acknowledgement"
      ]
    }

  [X] Override decision saved separately:
    +- User ID of reviewer
    +- Timestamp of decision
    +- Decision (approved / rejected)
    +- Rationale provided by reviewer
    +- All required fields completed


DATA PROTECTION
---------------
  [X] Patient Data (PII):
    +- Accessed via research_patient() (DB service)
    +- Never logged in full form (only summary in audit)
    +- Encrypted at rest (DB encryption)
    +- Encrypted in transit (TLS)
    +- Access limited to authenticated users

  [X] Evidence Sources:
    +- Retrieved from knowledge base
    +- Cached for performance
    +- No PII in evidence documents
    +- Cited in decision trace


SAFETY GATES
------------
  [X] Entry Gate (RequestGuardrails):
    +- Reject requests with downstream-use keywords

  [X] Evidence Gate (TargetSelection):
    +- Block if evidence quality insufficient (confidence < 0.4)

  [X] Validation Gate (Validation Node):
    +- Reject sequences with critical defects

  [X] Exit Gate (HumanGate):
    +- NO progression without clinician override


COMPLIANCE CHECKPOINTS
----------------------
  [X] HIPAA Compliance:
    +- Audit logs for all patient data access
    +- User authentication on all requests
    +- Encryption of PII
    +- No unauthorized data export

  [X] Research Governance:
    +- N-of-1 simulation (not clinical use)
    +- Human gate lock (cannot bypass)
    +- Evidence grounding (all claims cited)
    +- Risk assessment transparent

  [X] Data Governance:
    +- Access control (user_id tracking)
    +- Immutable audit trail
    +- Retention policies (archive after 12mo)
    +- Deletion on request
```

