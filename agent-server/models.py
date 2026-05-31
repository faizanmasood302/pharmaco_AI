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
    
    @model_validator(mode='before')
    @classmethod
    def encrypt_sensitive_fields(cls, values):
        # We only encrypt if we have the crypto module loaded and it's not a local seed
        try:
            from crypto import encrypt_pii
            if 'display_name' in values:
                values['display_name_encrypted'] = encrypt_pii(values['display_name'])
        except ImportError:
            pass
        return values


class PatientOut(BaseModel):
    id: str
    display_name: str
    age: int = Field(..., ge=0, le=120, description="Age 0-120")
    sex: str = Field(..., pattern="^[MFOU]$") # Male, Female, Other, Unknown
    indication: str
    cyp_profiles: list[CypProfileOut]

    @classmethod
    def from_db(cls, db_record: dict):
        """Construct from database record (decrypt fields if encrypted)"""
        try:
            from crypto import decrypt_pii
            # If the database returns the encrypted field, decrypt it
            if 'display_name_encrypted' in db_record:
                name = decrypt_pii(db_record['display_name_encrypted'])
            else:
                name = db_record.get('display_name', 'Unknown')
        except ImportError:
            name = db_record.get('display_name', 'Unknown')

        return cls(
            id=db_record['id'],
            display_name=name,
            age=db_record['age'],
            sex=db_record['sex'],
            indication=db_record.get('indication', ''),
            cyp_profiles=db_record.get('cyp_profiles', [])
        )


class PrescriptionRequest(BaseModel):
    patient_id: str
    medication: str = Field(..., description="Proposed medication name")


class EvaluationResponse(BaseModel):
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
    logic_tree: dict[str, Any] = Field(default_factory=dict, description="Structured logic graph for UI visualization")
    override_requirement: OverrideRequirement = Field(
        default_factory=lambda: OverrideRequirement(
            required=False,
            reason="No override requirement generated.",
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


EvaluationResponse.model_rebuild()
