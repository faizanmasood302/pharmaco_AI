from __future__ import annotations

import time

from pgx.rules import RiskAssessment, RiskLevel


def critique_prescription(
    assessment: RiskAssessment,
) -> tuple[RiskAssessment, str, int]:
    """Critic Agent: confirm flag and safe alternative for severe mismatches."""
    start = time.perf_counter()

    if assessment.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        summary = (
            f"PRESCRIPTION BLOCKED — {assessment.risk_level.value.upper()} risk. "
            f"Recommend: {assessment.recommended_alternative or 'clinical review'}."
        )
    elif assessment.flagged:
        summary = (
            f"Prescription flagged ({assessment.risk_level.value}). "
            "Physician override requires documented rationale."
        )
    else:
        summary = "No PGx contraindication. Prescription may proceed with standard monitoring."

    elapsed = int((time.perf_counter() - start) * 1000)
    return assessment, summary, elapsed
