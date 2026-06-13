from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

CORE_TERMS = {
    "mrna",
    "therapy",
    "target",
    "candidate",
    "sequence",
    "validation",
    "safety",
    "human",
    "review",
    "research",
    "simulation",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _load_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts = [
            part.strip() for part in re.split(r"\n(?=## |\# )", text) if part.strip()
        ]
        for index, part in enumerate(parts):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.name}:{index + 1}",
                    "text": part,
                }
            )
    return chunks


def _score_chunk(chunk: dict[str, Any], query_terms: set[str]) -> int:
    chunk_terms = _tokenize(chunk["text"])
    source_terms = _tokenize(chunk["source"].replace("_", " "))
    overlap = len(query_terms & chunk_terms)
    core_overlap = len(CORE_TERMS & chunk_terms)
    source_overlap = len(query_terms & source_terms)
    return (overlap * 3) + core_overlap + source_overlap


def _snippet(text: str, limit: int = 360) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def retrieve_therapy_evidence(
    target_disease: str,
    patient_context: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Retrieve source-grounded context for the n-of-1 research workflow."""
    start = time.perf_counter()
    # Exclude very common terms from the "must-match" disease set
    stop_terms = {
        "disease",
        "research",
        "simulation",
        "therapy",
        "target",
        "patient",
        "clinical",
    }
    disease_terms = _tokenize(target_disease) - stop_terms

    phenotype_terms = {
        profile.get("phenotype", "")
        for profile in patient_context.get("cyp_profiles", [])
        if isinstance(profile, dict)
    }
    general_terms = _tokenize(
        "mRNA therapy target validation safety human review research simulation"
    )
    query_terms = (
        _tokenize(target_disease)
        | _tokenize(patient_context.get("indication", ""))
        | _tokenize(" ".join(phenotype_terms))
        | general_terms
    )

    chunks = _load_chunks()
    ranked = []
    for chunk in chunks:
        score = _score_chunk(chunk, query_terms)
        # Bonus for specific disease-name overlap
        disease_overlap = (
            len(disease_terms & _tokenize(chunk["text"])) if disease_terms else 0
        )
        score += disease_overlap * 20
        if score > 0:
            ranked.append((score, chunk, disease_overlap))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:5]

    if not selected:
        return _low_quality_response(start)

    sources = sorted({chunk["source"] for _, chunk, _ in selected})
    total_disease_overlap = sum(d for _, _, d in selected)

    policy_present = any("n_of_1" in source for source in sources)

    # Logic: If a specific disease term was provided, it MUST be found in sources
    # to be considered moderate/high quality.
    if disease_terms and total_disease_overlap < 1:
        return _low_quality_response(start)

    if total_disease_overlap >= 3:
        evidence_quality = (
            "high" if len(sources) >= 2 and policy_present else "moderate"
        )
    elif total_disease_overlap >= 1 or not disease_terms:
        evidence_quality = "moderate"
    else:
        return _low_quality_response(start)

    elapsed = int((time.perf_counter() - start) * 1000)
    return (
        {
            "sources": sources,
            "target_rationale": (
                f"Retrieved {len(selected)} source chunks for {target_disease}. "
                "The evidence supports a simulated research candidate and "
                "requires human review."
            ),
            "known_risks": [
                "The candidate is not clinically validated.",
                "Sequence validation is deterministic but still a simulation.",
                "Disease-specific target evidence may be incomplete.",
            ],
            "open_questions": [
                "Is the target disease mechanism sufficiently documented?",
                "Does the reviewer accept the validation thresholds?",
            ],
            "evidence_quality": evidence_quality,
            "source_snippets": [
                {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                    "score": score,
                    "snippet": _snippet(chunk["text"]),
                }
                for score, chunk, _ in selected
            ],
        },
        elapsed,
    )


def _low_quality_response(start_time: float) -> tuple[dict[str, Any], int]:
    elapsed = int((time.perf_counter() - start_time) * 1000)
    return (
        {
            "sources": [],
            "target_rationale": (
                "No disease-specific evidence was retrieved. The system cannot "
                "reliably identify a therapeutic target for this indication."
            ),
            "known_risks": ["Insufficient source grounding for target selection."],
            "open_questions": [
                "Which reviewed disease mechanism supports this target?"
            ],
            "evidence_quality": "low",
            "source_snippets": [],
        },
        elapsed,
    )
