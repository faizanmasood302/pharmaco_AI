from __future__ import annotations

import hashlib
import time
from typing import Any

BALANCED_CODONS = (
    "GCU",
    "GAA",
    "CAA",
    "UGG",
    "AUC",
    "GAC",
    "AAA",
    "CGU",
    "UAC",
    "CCA",
)
LOW_GC_CODONS = ("AAU", "AUA", "UUA", "CAA", "GAA", "UAU", "AUC", "AAA")


def design_mrna_therapy(
    patient_profile: dict | None,
    target_disease: str,
    feedback: str | None = None,
) -> tuple[str, str, int]:
    """
    The Generative Agent (The Designer)
    Drafts the actual biological code (mRNA sequence) targeting the patient's disease.
    """
    start = time.time()
    
    phenotype = "Unknown"
    if (
        patient_profile
        and "cyp_profiles" in patient_profile
        and patient_profile["cyp_profiles"]
    ):
        phenotype = patient_profile["cyp_profiles"][0]["phenotype"]
    
    # Mocking base structural generation of an mRNA sequence based on constraints
    sequence = "AUG" + "GCA" * 15 + "UAA"
    
    rationale = (
        f"Drafted candidate mRNA sequence for {target_disease} optimized "
        f"for {phenotype} metabolizer. "
    )
    
    if feedback:
        rationale += f"Incorporated previous validation feedback: {feedback}."
        # Slightly alter the sequence to mock a deterministic change based on feedback
        sequence = "AUG" + "GCC" * 15 + "UAA"
        
    duration_ms = int((time.time() - start) * 1000)
    
    return sequence, rationale, duration_ms


def _stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _patient_phenotype(patient_profile: dict[str, Any] | None) -> str:
    if patient_profile and patient_profile.get("cyp_profiles"):
        return patient_profile["cyp_profiles"][0].get("phenotype", "Unknown")
    return "Unknown"


def design_research_mrna_candidate(
    patient_profile: dict[str, Any] | None,
    target_disease: str,
    evidence_bundle: dict[str, Any],
    *,
    iteration: int,
    revision_hints: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a deterministic simulated mRNA candidate for research review."""
    start = time.perf_counter()
    hints = revision_hints or []
    phenotype = _patient_phenotype(patient_profile)
    sources = evidence_bundle.get("sources", [])
    use_low_gc = any("gc" in hint.lower() for hint in hints)
    codon_pool = LOW_GC_CODONS if use_low_gc else BALANCED_CODONS

    patient_id = patient_profile.get("id") if patient_profile else "unknown"
    seed = f"{patient_id}:{target_disease}:{iteration}:{'|'.join(hints)}"
    offset = _stable_index(seed, len(codon_pool))
    body_codons = [
        codon_pool[(offset + index) % len(codon_pool)]
        for index in range(18)
    ]
    sequence = "AUG" + "".join(body_codons) + "UAA"
    sequence_hash = hashlib.sha256(sequence.encode("utf-8")).hexdigest()[:12]
    candidate_id = f"therapy-cand-{sequence_hash}-{iteration}"

    constraints = [
        "research simulation only",
        "RNA alphabet only",
        "AUG start codon",
        "terminal stop codon",
        "no intentional internal stop codons",
        "deterministic validation required",
        "human review required",
    ]
    if hints:
        constraints.extend(f"revision: {hint}" for hint in hints)

    candidate = {
        "candidate_id": candidate_id,
        "iteration": iteration,
        "modality": "simulated_mrna",
        "sequence": sequence,
        "design_constraints": constraints,
        "rationale": (
            f"Drafted a simulated mRNA candidate for {target_disease} using "
            f"patient phenotype context ({phenotype}) and retrieved research "
            f"evidence from {', '.join(sources) if sources else 'no sources'}."
        ),
        "evidence_refs": sources,
    }
    elapsed = int((time.perf_counter() - start) * 1000)
    return candidate, elapsed
