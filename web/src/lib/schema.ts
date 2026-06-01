import { z } from 'zod';

export const AgentStepSchema = z.object({
  agent: z.string(),
  status: z.string(),
  summary: z.string(),
  duration_ms: z.number().nullable().optional(),
  confidence: z.number().nullable().optional(),
  evidence_refs: z.array(z.string()).optional(),
});

export const AuditEventSchema = z.object({
  stage: z.string(),
  decision: z.string(),
  rationale: z.string(),
  requires_human_review: z.boolean(),
});

export const OverrideRequirementSchema = z.object({
  required: z.boolean(),
  reason: z.string(),
  required_fields: z.array(z.string()),
});

export const HumanGateSchema = z.object({
  required: z.boolean(),
  status: z.string(),
  reason: z.string(),
  review_notes: z.string().nullable().optional(),
  reviewed_by: z.string().nullable().optional(),
  reviewed_at: z.string().nullable().optional(),
  required_fields: z.array(z.string()),
});

export const CypProfileSchema = z.object({
  gene: z.string(),
  diplotype: z.string(),
  phenotype: z.string(),
  activity_score: z.string(),
});

export const PatientSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  age: z.number(),
  sex: z.string(),
  indication: z.string(),
  cyp_profiles: z.array(CypProfileSchema),
});

export const MedicationSchema = z.object({
  name: z.string(),
  enzyme: z.string(),
  is_prodrug: z.boolean(),
});

export const PatientListItemSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  indication: z.string(),
  phenotype: z.string(),
});

export const CheckInSchema = z.object({
  id: z.string(),
  plan_id: z.string(),
  day_offset: z.number(),
  prompt: z.string(),
  status: z.string(),
  response: z.string().nullable(),
  side_effect_reported: z.boolean(),
  created_at: z.string().optional(),
});

export const AdherencePlanSchema = z.object({
  id: z.string().optional(),
  plan_id: z.string().optional(),
  patient_id: z.string(),
  medication: z.string(),
  check_ins: z.array(CheckInSchema),
  message: z.string().optional(),
  created_at: z.string().optional(),
});

export const EvaluationHistoryItemSchema = z.object({
  id: z.string().optional(),
  patient_id: z.string(),
  medication: z.string(),
  flagged: z.boolean(),
  risk_level: z.string(),
  created_at: z.string().optional(),
});

export const EvaluationResultSchema = z.object({
  evaluation_id: z.string().nullable().optional(),
  status: z.string(),
  patient_id: z.string(),
  medication: z.string(),
  flagged: z.boolean(),
  risk_level: z.string(),
  risk_summary: z.string(),
  pathways: z.array(z.string()),
  recommended_alternative: z.string().nullable(),
  alternative_rationale: z.string(),
  cpic_note: z.string(),
  cpic_level: z.string().optional(),
  patient: PatientSchema.nullable(),
  agent_steps: z.array(AgentStepSchema),
  clinical_narrative: z.string().nullable(),
  clinical_evidence: z.string().nullable(),
  evidence_sources: z.array(z.string()),
  decision_confidence: z.number(),
  safety_notes: z.array(z.string()),
  agent_verdict: z.string(),
  audit_trail: z.array(AuditEventSchema),
  logic_tree: z.any().optional(),
  override_requirement: OverrideRequirementSchema,
  human_gate: HumanGateSchema,
  next_best_actions: z.array(z.string()),
});

export type ValidatedEvaluationResult = z.infer<typeof EvaluationResultSchema>;

export const TherapyEvidenceBundleSchema = z.object({
  sources: z.array(z.string()),
  target_rationale: z.string(),
  known_risks: z.array(z.string()),
  open_questions: z.array(z.string()),
  evidence_quality: z.string(),
  source_snippets: z.array(z.object({
    source: z.string(),
    chunk_id: z.string(),
    score: z.number(),
    snippet: z.string(),
  })),
});

export const TherapyCandidateSchema = z.object({
  candidate_id: z.string(),
  iteration: z.number(),
  modality: z.string(),
  sequence: z.string(),
  design_constraints: z.array(z.string()),
  rationale: z.string(),
  evidence_refs: z.array(z.string()),
});

export const TherapyValidationCheckSchema = z.object({
  name: z.string(),
  passed: z.boolean(),
  score: z.number(),
  detail: z.string(),
  severity: z.string(),
});

export const TherapyValidationResultSchema = z.object({
  passed: z.boolean(),
  overall_risk_score: z.number(),
  checks: z.array(TherapyValidationCheckSchema),
  blocked_reasons: z.array(z.string()),
  revision_hints: z.array(z.string()),
});

export const TherapyGenerationResultSchema = z.object({
  status: z.string(),
  patient_id: z.string(),
  target_disease: z.string(),
  mrna_sequence: z.string().nullable(),
  toxicity_score: z.number().nullable(),
  iterations: z.number(),
  agent_steps: z.array(AgentStepSchema),
  clinical_narrative: z.string(),
  therapy_request_id: z.string().nullable().optional(),
  candidate_id: z.string().nullable().optional(),
  final_candidate: TherapyCandidateSchema.nullable(),
  candidate_history: z.array(TherapyCandidateSchema),
  validation_result: TherapyValidationResultSchema.nullable(),
  evidence_bundle: TherapyEvidenceBundleSchema.nullable(),
  evidence_sources: z.array(z.string()),
  safety_notes: z.array(z.string()),
  audit_trail: z.array(AuditEventSchema),
  logic_tree: z.any().optional(),
  human_gate: HumanGateSchema,
});

export type ValidatedTherapyGenerationResult = z.infer<typeof TherapyGenerationResultSchema>;
