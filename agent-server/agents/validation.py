from __future__ import annotations

import os
import random
import time
from typing import Any

# Use a frozenset for O(1) membership testing and clear semantic intent
SAFE_DRUGS = frozenset(
    {
        "Duloxetine",
        "Pregabalin",
        "Prasugrel",
        "Ticagrelor",
        "Acetaminophen (scheduled)",
        "Sertraline",
        "Bupropion",
        "Ibuprofen",
    }
)
RNA_ALPHABET = frozenset({"A", "U", "G", "C"})
STOP_CODONS = frozenset({"UAA", "UAG", "UGA"})


def validate_drug_safety(drug: str) -> tuple[bool, float, str, int]:
    """
    Validates the safety of a proposed drug using deterministic rules.
    """
    start = time.time()

    # If the drug is explicitly in our safe list, mark it safe. Otherwise, 0.8 toxicity.
    toxicity_score = 0.2 if drug in SAFE_DRUGS else 0.8
    duration_ms = int((time.time() - start) * 1000)

    if toxicity_score > 0.5:
        is_safe = False
        feedback = (
            f"{drug} failed safety validation "
            f"(mock toxicity score: {toxicity_score:.2f})."
        )
    else:
        is_safe = True
        feedback = (
            f"{drug} passed safety validation. Toxicity score: {toxicity_score:.2f}."
        )

    return is_safe, toxicity_score, feedback, duration_ms


def validate_mrna_sequence(sequence: str) -> tuple[bool, float, str, int]:
    """
    The Validation Agent (The Safety Guardrail)
    Connects to deterministic, physics-based biological simulators.
    Runs 'in-silico' tests to see if the generated mRNA will fold correctly or be toxic.
    """
    start = time.time()

    # Mocking in-silico physics-based simulation
    # Fixed Remaining Issue: Allow deterministic overrides for testing
    mock_override = os.environ.get("MOCK_MRNA_TOXICITY")
    if mock_override is not None:
        try:
            toxicity_score = float(mock_override)
        except ValueError:
            toxicity_score = random.uniform(0.1, 0.9)
    else:
        toxicity_score = random.uniform(0.1, 0.9)

    duration_ms = int((time.time() - start) * 1000)

    # Set threshold at 0.5 to force occasional loops between generative and validation
    if toxicity_score > 0.5:
        is_safe = False
        feedback = (
            f"Sequence failed stability test with toxicity score {toxicity_score:.2f}. "
            "High probability of off-target binding. Redesign and optimize for lower "
            "free energy."
        )
    else:
        is_safe = True
        feedback = (
            "Sequence passed in-silico safety validation. "
            f"Toxicity score: {toxicity_score:.2f}. Folding structure stable."
        )

    return is_safe, toxicity_score, feedback, duration_ms


def _codons(sequence: str) -> list[str]:
    return [sequence[index : index + 3] for index in range(0, len(sequence), 3)]


def _gc_content(sequence: str) -> float:
    if not sequence:
        return 0.0
    return (sequence.count("G") + sequence.count("C")) / len(sequence)


def _repeat_risk(codons: list[str]) -> float:
    if not codons:
        return 1.0
    longest = 1
    current = 1
    for previous, current_codon in zip(codons, codons[1:], strict=False):
        if previous == current_codon:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest / len(codons)


def _check(
    name: str,
    passed: bool,
    score: float,
    detail: str,
    severity: str = "info",
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "score": max(0.0, min(1.0, score)),
        "detail": detail,
        "severity": severity,
    }


from agents.bioinformatics_adapter import (
    simulate_folding_energy,
    simulate_homology_search,
    simulate_immunogenicity_score,
)


def validate_research_mrna_candidate(sequence: str) -> tuple[dict[str, Any], int]:
    """Run deterministic checks and simulated bioinformatics for the n-of-1 research simulation."""
    start = time.perf_counter()
    normalized = sequence.upper().replace(" ", "").replace("\n", "")

    # Phase 4: Simulated Bioinformatics Integrations
    mfe = simulate_folding_energy(normalized)
    homology = simulate_homology_search(normalized)
    immunogenicity = simulate_immunogenicity_score(normalized)

    codons = _codons(normalized) if len(normalized) % 3 == 0 else []
    coding_codons = codons[1:-1] if len(codons) >= 2 else []
    internal_stop_count = sum(1 for codon in coding_codons if codon in STOP_CODONS)
    gc = _gc_content(normalized)
    repeat_risk = _repeat_risk(coding_codons)

    checks = [
        _check(
            "rna_alphabet",
            set(normalized).issubset(RNA_ALPHABET),
            1.0 if set(normalized).issubset(RNA_ALPHABET) else 0.0,
            "Sequence uses only A, U, G, and C.",
            "critical",
        ),
        _check(
            "reading_frame",
            len(normalized) >= 30 and len(normalized) % 3 == 0,
            1.0 if len(normalized) >= 30 and len(normalized) % 3 == 0 else 0.0,
            f"Sequence length is {len(normalized)} bases.",
            "critical",
        ),
        _check(
            "folding_stability",
            mfe <= -25.0,
            1.0 if mfe <= -25.0 else 0.5,
            f"Predicted MFE is {mfe} kcal/mol (threshold: -25.0).",
            "warning",
        ),
        _check(
            "homology_off_target",
            not homology,
            1.0 if not homology else 0.4,
            f"Detected {len(homology)} potential off-target homologies."
            if homology
            else "No high-identity homologies detected.",
            "warning",
        ),
        _check(
            "immunogenicity_risk",
            immunogenicity <= 0.4,
            1.0 - immunogenicity,
            f"Predicted immunogenicity score is {immunogenicity:.2f}.",
            "warning",
        ),
        _check(
            "start_codon",
            normalized.startswith("AUG"),
            1.0 if normalized.startswith("AUG") else 0.0,
            "Sequence starts with AUG.",
            "critical",
        ),
        _check(
            "terminal_stop",
            bool(codons and codons[-1] in STOP_CODONS),
            1.0 if codons and codons[-1] in STOP_CODONS else 0.0,
            "Sequence ends with a terminal stop codon.",
            "critical",
        ),
        _check(
            "internal_stop_codons",
            internal_stop_count == 0,
            1.0 if internal_stop_count == 0 else 0.0,
            f"Detected {internal_stop_count} internal stop codons.",
            "critical",
        ),
        _check(
            "gc_content",
            0.35 <= gc <= 0.70,
            1.0 - min(abs(gc - 0.52), 0.52),
            f"GC content is {gc:.2f}; accepted demo range is 0.35-0.70.",
            "warning",
        ),
        _check(
            "repeat_motif_risk",
            repeat_risk <= 0.30,
            1.0 - repeat_risk,
            f"Longest repeated codon run ratio is {repeat_risk:.2f}.",
            "warning",
        ),
    ]

    blocked_reasons = [
        check["detail"]
        for check in checks
        if not check["passed"] and check["severity"] == "critical"
    ]
    # Block on specific warnings for the research simulation
    if not checks[2]["passed"]:  # folding
        blocked_reasons.append(checks[2]["detail"])
    if not checks[8]["passed"]:  # gc
        blocked_reasons.append(checks[8]["detail"])

    revision_hints: list[str] = []
    if not checks[0]["passed"]:
        revision_hints.append("Use only RNA bases A, U, G, and C.")
    if not checks[1]["passed"]:
        revision_hints.append("Keep the sequence in-frame and at least 30 bases long.")
    if mfe > -25.0:
        revision_hints.append(
            "Optimize sequence for higher folding stability (lower MFE)."
        )
    if homology:
        revision_hints.append("Modify sequence to avoid known off-target homologies.")
    if immunogenicity > 0.4:
        revision_hints.append("Reduce immunogenic motif density.")
    if not checks[5]["passed"]:
        revision_hints.append("Add an AUG start codon.")
    if not checks[6]["passed"]:
        revision_hints.append("Add a valid terminal stop codon.")
    if internal_stop_count:
        revision_hints.append("Remove internal stop codons from the coding region.")
    if gc > 0.70:
        revision_hints.append("Reduce GC content.")
    elif gc < 0.35:
        revision_hints.append("Increase GC content.")
    if repeat_risk > 0.30:
        revision_hints.append("Diversify repeated codons.")

    failure_weight = sum(0.12 for check in checks if not check["passed"])
    risk_score = min(
        1.0,
        0.10
        + failure_weight
        + (repeat_risk * 0.15)
        + (immunogenicity * 0.20)
        + min(abs(gc - 0.52), 0.25),
    )
    passed = not blocked_reasons and risk_score <= 0.50
    elapsed = int((time.perf_counter() - start) * 1000)
    return (
        {
            "passed": passed,
            "overall_risk_score": round(risk_score, 2),
            "checks": checks,
            "blocked_reasons": blocked_reasons,
            "revision_hints": revision_hints,
            "validator_version": "1.4.2-research",
        },
        elapsed,
    )
