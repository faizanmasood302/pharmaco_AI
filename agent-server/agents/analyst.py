from __future__ import annotations

import time

from pgx.patients import PatientRecord
from pgx.rules import RiskAssessment, assess_prescription


def analyze_risk(
    patient_id: str, medication: str, patient: PatientRecord | None
) -> tuple[RiskAssessment, str, int]:
    """Analyst Agent: deterministic pathway cross-reference."""
    start = time.perf_counter()
    assessment = assess_prescription(patient_id, medication, patient=patient)
    elapsed = int((time.perf_counter() - start) * 1000)

    if patient:
        phenotype = patient["cyp_profiles"][0]["phenotype"]
        summary = (
            f"Cross-referenced {medication} against {phenotype} — "
            f"risk level {assessment.risk_level.value}."
        )
    else:
        summary = assessment.risk_summary

    return assessment, summary, elapsed
