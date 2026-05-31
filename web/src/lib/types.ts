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

export interface OverrideRequirement {
  required: boolean;
  reason: string;
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
  logic_tree?: any;
  override_requirement: OverrideRequirement;
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
