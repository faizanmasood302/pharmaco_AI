export interface AgentStep {
  agent: string;
  status: string;
  summary: string;
  duration_ms?: number | null;
  confidence?: number | null;
  evidence_refs?: string[];
}

export interface AuditEvent {
  stage: string;
  decision: string;
  rationale: string;
  requires_human_review: boolean;
}

export interface LogicTreeNodeData {
  node: string;
  detail?: string;
  flag?: boolean;
  children?: LogicTreeNodeData[];
}

export interface OverrideRequirement {
  required: boolean;
  reason: string;
  required_fields: string[];
}

export interface HumanGate {
  required: boolean;
  status: string;
  reason: string;
  review_notes?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  required_fields: string[];
}

export interface CypProfile {
  gene: string;
  diplotype: string;
  phenotype: string;
  activity_score: string;
}

export interface Patient {
  id: string;
  display_name: string;
  age: number;
  sex: string;
  indication: string;
  cyp_profiles: CypProfile[];
  created_at?: string;
}

export interface EvaluationResult {
  evaluation_id?: string | null;
  status: string;
  patient_id: string;
  medication: string;
  flagged: boolean;
  risk_level: string;
  risk_summary: string;
  pathways: string[];
  recommended_alternative: string | null;
  alternative_rationale: string;
  cpic_note: string;
  cpic_level?: string;
  patient: Patient | null;
  agent_steps: AgentStep[];
  clinical_narrative: string | null;
  clinical_evidence: string | null;
  evidence_sources: string[];
  decision_confidence: number;
  safety_notes: string[];
  agent_verdict: string;
  audit_trail: AuditEvent[];
  logic_tree?: LogicTreeNodeData | null;
  override_requirement: OverrideRequirement;
  human_gate: HumanGate;
  next_best_actions: string[];
  created_at?: string;
}

export interface EvaluationHistoryItem {
  id?: string;
  patient_id: string;
  medication: string;
  flagged: boolean;
  risk_level: string;
  created_at?: string;
}

export interface CheckIn {
  id: string;
  plan_id: string;
  day_offset: number;
  prompt: string;
  status: string;
  response: string | null;
  side_effect_reported: boolean;
  created_at?: string;
}

export interface AdherencePlan {
  id?: string;
  plan_id?: string;
  patient_id: string;
  medication: string;
  check_ins: CheckIn[];
  message?: string;
  created_at?: string;
}

export interface PatientListItem {
  id: string;
  display_name: string;
  indication: string;
  phenotype: string;
}

export interface Medication {
  name: string;
  enzyme: string;
  is_prodrug: boolean;
}

export interface ClinicalReport {
  id: string;
  evaluation_id: string;
  patient_id: string;
  clinician_id?: string | null;
  content: string;
  status?: string;
  created_at: string;
  updated_at?: string;
}

export interface TherapyEvidenceBundle {
  sources: string[];
  target_rationale: string;
  known_risks: string[];
  open_questions: string[];
  evidence_quality: string;
  source_snippets: Array<{
    source: string;
    chunk_id: string;
    score: number;
    snippet: string;
  }>;
}

export interface TherapyCandidate {
  candidate_id: string;
  iteration: number;
  modality: string;
  sequence: string;
  design_constraints: string[];
  rationale: string;
  evidence_refs: string[];
}

export interface TherapyValidationCheck {
  name: string;
  passed: boolean;
  score: number;
  detail: string;
  severity: string;
}

export interface TherapyValidationResult {
  passed: boolean;
  overall_risk_score: number;
  checks: TherapyValidationCheck[];
  blocked_reasons: string[];
  revision_hints: string[];
}

export interface TherapyGenerationResult {
  status: string;
  patient_id: string;
  target_disease: string;
  mrna_sequence: string | null;
  toxicity_score: number | null;
  iterations: number;
  agent_steps: AgentStep[];
  clinical_narrative: string;
  therapy_request_id?: string | null;
  candidate_id?: string | null;
  final_candidate: TherapyCandidate | null;
  candidate_history: TherapyCandidate[];
  validation_result: TherapyValidationResult | null;
  evidence_bundle: TherapyEvidenceBundle | null;
  evidence_sources: string[];
  safety_notes: string[];
  audit_trail: AuditEvent[];
  logic_tree?: LogicTreeNodeData | null;
  human_gate: HumanGate;
}
