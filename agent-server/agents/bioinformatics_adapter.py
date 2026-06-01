from __future__ import annotations

import hashlib
import time
from typing import Any


def simulate_folding_energy(sequence: str) -> float:
    """Simulate a MFE (Minimum Free Energy) calculation for RNA folding."""
    # Deterministic but pseudo-random energy based on sequence
    seed = hashlib.sha256(sequence.encode("utf-8")).hexdigest()
    base_energy = -20.0 - (int(seed[:4], 16) % 30)
    # Penalize GC content imbalance
    gc = (sequence.count("G") + sequence.count("C")) / len(sequence) if sequence else 0.5
    penalty = abs(gc - 0.52) * 50
    return round(base_energy + penalty, 2)


def simulate_homology_search(sequence: str) -> list[dict[str, Any]]:
    """Simulate a BLAST-like homology search for off-target risks."""
    # Deterministic mock results
    if "AAAAA" in sequence:
        return [{"target": "Poly-A binding protein region", "identity": 0.85, "e_value": 1e-5}]
    return []


def simulate_immunogenicity_score(sequence: str) -> float:
    """Simulate a predicted immunogenicity score."""
    # Simple heuristic for demo
    motifs = ("UGUGU", "GUCCUUCAA", "UGU")
    count = sum(sequence.count(m) for m in motifs)
    return min(1.0, count * 0.15)
