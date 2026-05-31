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
  next_best_actions: z.array(z.string()),
});

export type ValidatedEvaluationResult = z.infer<typeof EvaluationResultSchema>;
