from __future__ import annotations

import time

from models import AuditEvent, OverrideRequirement
from pgx.rules import RiskAssessment, RiskLevel


def challenge_decision(
    medication: str,
    phenotype: str,
    assessment: RiskAssessment,
    evidence_sources: list[str],
) -> tuple[list[AuditEvent], OverrideRequirement, list[str], str, str, int, float]:
    """Safety Challenge Agent: stress-test the proposed decision before release."""
    start = time.perf_counter()

    audit = [
        AuditEvent(
            stage="identity_and_genotype",
            decision="pass" if phenotype != "Unknown" else "needs_review",
            rationale=(
                f"CYP phenotype available: {phenotype}."
                if phenotype != "Unknown"
                else "No CYP phenotype available for patient."
            ),
            requires_human_review=phenotype == "Unknown",
        ),
        AuditEvent(
            stage="evidence_grounding",
            decision="pass" if evidence_sources else "needs_review",
            rationale=(
                f"Decision grounded in {', '.join(evidence_sources)}."
                if evidence_sources
                else "No local evidence source matched the case."
            ),
            requires_human_review=not evidence_sources,
        ),
    ]

    high_risk = assessment.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    audit.append(
        AuditEvent(
            stage="safety_challenge",
            decision="block" if high_risk else "approve_with_monitoring",
            rationale=(
                "Severe PGx mismatch detected; dispensing should be blocked unless an override is documented."
                if high_risk
                else "No severe PGx mismatch detected by the deterministic rule engine."
            ),
            requires_human_review=high_risk,
        )
    )

    override = OverrideRequirement(
        required=high_risk,
        reason=(
            "Critical/high PGx risk requires clinician override documentation."
            if high_risk
            else "No override required by the current PGx rule set."
        ),
        required_fields=[
            "clinician_id",
            "risk_benefit_rationale",
            "patient_counseling_attestation",
            "monitoring_plan",
        ]
        if high_risk
        else [],
    )

    if high_risk:
        actions = [
            "Hold dispensing until clinician review is documented.",
            f"Switch to {assessment.recommended_alternative or 'a non-CYP2D6-dependent alternative'} if clinically appropriate.",
            "Record patient counseling and monitoring plan before release.",
        ]
        verdict = "blocked_pending_override"
        summary = "Challenge agent upheld the block and generated override controls."
        confidence = 0.93 if evidence_sources else 0.78
    elif assessment.flagged:
        actions = [
            "Require clinician review before dispensing.",
            "Use lowest effective dose and monitor response within 72 hours.",
        ]
        verdict = "review_required"
        summary = "Challenge agent confirmed a moderate risk review path."
        confidence = 0.84
    else:
        actions = [
            "Proceed with standard monitoring.",
            "Offer adherence monitoring after dispensing.",
        ]
        verdict = "approved_with_monitoring"
        summary = "Challenge agent found no blocking PGx safety issue."
        confidence = 0.82

    elapsed = int((time.perf_counter() - start) * 1000)
    return audit, override, actions, verdict, summary, elapsed, confidence
