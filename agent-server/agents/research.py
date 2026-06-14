from __future__ import annotations

import time

from db.database import get_patient_by_id
from exceptions import InvalidPhenotypeError, PatientNotFoundError
from pgx.patients import PatientRecord


def research_patient(patient_id: str) -> tuple[PatientRecord | None, str, int]:
    """Research Agent: load n-of-1 phenotype from Supabase or seed fallback."""
    start = time.perf_counter()
    patient = get_patient_by_id(patient_id)
    elapsed = int((time.perf_counter() - start) * 1000)

    if patient is None:
        # Halt the pipeline immediately and return a typed 404 error
        raise PatientNotFoundError(patient_id)

    # Fixed Bug #3: Safe array access for cyp_profiles
    if not patient.get("cyp_profiles"):
        raise InvalidPhenotypeError(patient_id, gene="ANY")

    profile = patient["cyp_profiles"][0]
    phenotype = profile["phenotype"]
    gene = profile["gene"]

    summary = (
        f"Retrieved FHIR-linked profile for {patient['display_name']}: "
        f"{gene} {phenotype}."
    )
    return patient, summary, elapsed
