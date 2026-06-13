from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentStep(BaseModel):
    agent: str
    status: str
    summary: str
    duration_ms: int | None = None
    confidence: float | None = Field(
        default=None, ge=0, le=1, description="Agent confidence from 0 to 1"
    )
    evidence_refs: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    stage: str
    decision: str
    rationale: str
    requires_human_review: bool = False


class OverrideRequirement(BaseModel):
    required: bool
    reason: str
    required_fields: list[str] = Field(default_factory=list)


class HumanGate(BaseModel):
    required: bool
    status: str = "pending"
    reason: str
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    required_fields: list[str] = Field(default_factory=list)


class CypProfileOut(BaseModel):
    gene: str
    diplotype: str
    phenotype: str
    activity_score: str


class PatientIn(BaseModel):
    """Patient data on input (encrypted before storage)"""

    id: str
    display_name: str
    display_name_encrypted: str | None = None
    age: int
    sex: str
    indication: str
    cyp_profiles: list[CypProfileOut]

    @model_validator(mode="before")
    @classmethod
    def encrypt_sensitive_fields(cls, values):
        # We only encrypt if we have the crypto module loaded and it's not a local seed
        try:
            from crypto import encrypt_pii

            if "display_name" in values:
                values["display_name_encrypted"] = encrypt_pii(values["display_name"])
        except ImportError:
            pass
        return values


class PatientOut(BaseModel):
    id: str
    display_name: str
    age: int = Field(..., ge=0, le=120, description="Age 0-120")
    sex: str = Field(..., pattern="^[MFOU]$")  # Male, Female, Other, Unknown
    indication: str
    cyp_profiles: list[CypProfileOut]

    @classmethod
    def from_db(cls, db_record: dict):
        """Construct from database record (decrypt fields if encrypted)"""
        try:
            from crypto import decrypt_pii

            # If the database returns the encrypted field, decrypt it
            if "display_name_encrypted" in db_record:
                name = decrypt_pii(db_record["display_name_encrypted"])
            else:
                name = db_record.get("display_name", "Unknown")
        except ImportError:
            name = db_record.get("display_name", "Unknown")

        return cls(
            id=db_record["id"],
            display_name=name,
            age=db_record["age"],
            sex=db_record["sex"],
            indication=db_record.get("indication", ""),
            cyp_profiles=db_record.get("cyp_profiles", []),
        )


class PrescriptionRequest(BaseModel):
    patient_id: str
    medication: str = Field(..., description="Proposed medication name")


class ReasoningOutput(BaseModel):
    flagged: bool
    risk_level: str
    risk_summary: str
    recommended_alternative: str | None = None
    alternative_rationale: str
    cpic_note: str
    cpic_level: str = "informative"
    decision_confidence: float = Field(default=0.72, ge=0, le=1)
    next_best_actions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    human_gate_required: bool = True


class CriticOutput(BaseModel):
    agent_verdict: str
    critique_summary: str
    audit_trail: list[AuditEvent] = Field(default_factory=list)
    override_requirement: OverrideRequirement = Field(
        default_factory=lambda: OverrideRequirement(
            required=True,
            reason="Clinician review required before release.",
            required_fields=[
                "clinician_id",
                "risk_benefit_rationale",
                "patient_counseling_attestation",
                "monitoring_plan",
            ],
        )
    )
    next_best_actions: list[str] = Field(default_factory=list)
    challenge_confidence: float = Field(default=0.8, ge=0, le=1)
    human_gate_required: bool = True


class EvaluationResponse(BaseModel):
    evaluation_id: str | None = None
    status: str
    patient_id: str
    medication: str
    flagged: bool
    risk_level: str
    risk_summary: str
    pathways: list[str]
    recommended_alternative: str | None
    alternative_rationale: str
    cpic_note: str
    cpic_level: str = "informative"
    patient: PatientOut | None
    agent_steps: list[AgentStep]
    clinical_narrative: str | None = None
    clinical_evidence: str | None = None
    evidence_sources: list[str] = Field(default_factory=list)
    decision_confidence: float = Field(default=0.75, ge=0, le=1)
    safety_notes: list[str] = Field(default_factory=list)
    agent_verdict: str = "review"
    audit_trail: list[AuditEvent] = Field(default_factory=list)
    logic_tree: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured logic graph for UI visualization",
    )
    override_requirement: OverrideRequirement = Field(
        default_factory=lambda: OverrideRequirement(
            required=False,
            reason="No override requirement generated.",
        )
    )
    human_gate: HumanGate = Field(
        default_factory=lambda: HumanGate(
            required=True,
            status="pending",
            reason="Clinician review required before release.",
        )
    )
    next_best_actions: list[str] = Field(default_factory=list)


class FhirIngestRequest(BaseModel):
    bundle: dict = Field(..., description="FHIR R4 Bundle JSON")


class AdherencePlanRequest(BaseModel):
    patient_id: str
    medication: str


class CheckInSubmitRequest(BaseModel):
    response: str
    side_effect_reported: bool = False


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(..., description="Clinician decision: approved or rejected")
    reviewer: str | None = None
    rationale: str | None = None


EvaluationResponse.model_rebuild()


class TherapyEvidenceBundle(BaseModel):
    sources: list[str] = Field(default_factory=list)
    target_rationale: str
    known_risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    evidence_quality: str = "low"
    source_snippets: list[dict[str, Any]] = Field(default_factory=list)


class TherapyCandidate(BaseModel):
    candidate_id: str
    iteration: int
    modality: str = "simulated_mrna"
    sequence: str
    design_constraints: list[str] = Field(default_factory=list)
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class TherapyValidationCheck(BaseModel):
    name: str
    passed: bool
    score: float = Field(default=0, ge=0, le=1)
    detail: str
    severity: str = "info"


class TherapyValidationResult(BaseModel):
    passed: bool
    overall_risk_score: float = Field(default=1, ge=0, le=1)
    checks: list[TherapyValidationCheck] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    revision_hints: list[str] = Field(default_factory=list)
    validator_version: str | None = None


class TherapyGenerationRequest(BaseModel):
    patient_id: str
    target_disease: str = Field(
        ...,
        description="Target condition or protein constraint",
    )
    max_iterations: int = Field(default=3, ge=1, le=5)


class TherapyGenerationResponse(BaseModel):
    status: str
    patient_id: str
    target_disease: str
    mrna_sequence: str | None = None
    toxicity_score: float | None = None
    iterations: int
    agent_steps: list[AgentStep]
    clinical_narrative: str
    therapy_request_id: str | None = None
    candidate_id: str | None = None
    final_candidate: TherapyCandidate | None = None
    candidate_history: list[TherapyCandidate] = Field(default_factory=list)
    validation_result: TherapyValidationResult | None = None
    evidence_bundle: TherapyEvidenceBundle | None = None
    evidence_sources: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    audit_trail: list[AuditEvent] = Field(default_factory=list)
    logic_tree: dict[str, Any] = Field(default_factory=dict)
    human_gate: HumanGate = Field(
        default_factory=lambda: HumanGate(
            required=True,
            status="pending",
            reason="Researcher or clinician review required before downstream use.",
            required_fields=[
                "reviewer_id",
                "research_rationale",
                "evidence_review_attestation",
                "safety_risk_acknowledgement",
            ],
        )
    )
