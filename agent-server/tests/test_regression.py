"""
Regression harness: runs evaluate_prescription() against all patient × drug
combinations with GROQ_API_KEY forced empty so every agent uses its fallback,
and database calls mocked to avoid NeonDB cold-start delays.

Asserts:
- No exception is raised for any combination
- Every response has a non-None risk_level
"""
from __future__ import annotations

import os
import sys
import traceback

import pytest

# Must be set BEFORE any imports — load_dotenv() won't overwrite it
os.environ["GROQ_API_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator_agent import evaluate_prescription
from pgx.rules import DRUG_RULES
from pgx.patients import PATIENTS


PATIENT_IDS = sorted(PATIENTS.keys())
DRUG_NAMES = sorted(DRUG_RULES.keys())

EXTRA_DRUGS = ["prasugrel", "ticagrelor", "acetaminophen", "ibuprofen", "nonexistent_drug"]


@pytest.mark.asyncio
async def test_misuse_nm_prodrug_not_flagged():
    """Regression: NM + prodrug opioid must return flagged=False (CPIC: standard dosing)."""
    import os
    had_key = os.environ.pop("GROQ_API_KEY", None)
    try:
        from agents.misuse_agent import evaluate_misuse_risk
        result = await evaluate_misuse_risk("PGX-003", "codeine")
        assert result.agent_name == "MisuseMonitor"
        assert result.flagged is False, (
            f"NM + codeine should not be flagged, got flagged={result.flagged}"
        )
        assert result.risk_level == "low", (
            f"NM + codeine should be low risk, got {result.risk_level}"
        )
    finally:
        if had_key is not None:
            os.environ["GROQ_API_KEY"] = had_key


@pytest.mark.asyncio
async def test_misuse_um_nonprodrug_not_flagged():
    """Regression: UM + non-prodrug opioid must return flagged=False (CPIC Level C, insufficient evidence)."""
    import os
    had_key = os.environ.pop("GROQ_API_KEY", None)
    try:
        from agents.misuse_agent import evaluate_misuse_risk
        result = await evaluate_misuse_risk("PGX-001", "hydrocodone")
        assert result.agent_name == "MisuseMonitor"
        assert result.flagged is False, (
            f"UM + hydrocodone should not be flagged (CPIC Level C), got flagged={result.flagged}"
        )
    finally:
        if had_key is not None:
            os.environ["GROQ_API_KEY"] = had_key


@pytest.mark.asyncio
async def test_adherence_pregabalin_not_flagged_for_phenotype():
    """Regression: Pregabalin (non-CYP, renally cleared) should never be flagged for CYP phenotype."""
    import os
    had_key = os.environ.pop("GROQ_API_KEY", None)
    try:
        from agents.adherence_agent import evaluate_adherence
        result = await evaluate_adherence("PGX-001", "pregabalin")
        assert result.agent_name == "Adherence"
        assert result.flagged is False, (
            f"Pregabalin should not be flagged for UM phenotype, got flagged={result.flagged}"
        )
        assert result.risk_level == "low", (
            f"Pregabalin should be low risk, got {result.risk_level}"
        )
    finally:
        if had_key is not None:
            os.environ["GROQ_API_KEY"] = had_key


@pytest.mark.asyncio
async def test_adherence_um_prodrug_no_normal_metabolizer_hallucination():
    """Regression: the adherence agent was previously documented to hallucinate
    'normal metabolizer' for ultra-rapid metabolizer patients when using the LLM
    path. This test pins that bug with GROQ_API_KEY forced empty (fallback path):
    UM + prodrug must return moderate/high risk, never low, and never mention 'normal'.
    """
    import os
    had_key = os.environ.pop("GROQ_API_KEY", None)
    try:
        from agents.adherence_agent import evaluate_adherence
        result = await evaluate_adherence("PGX-001", "codeine")
        assert result.agent_name == "Adherence"
        assert result.risk_level in ("moderate", "high"), (
            f"UM + prodrug should never be low risk, got {result.risk_level}"
        )
        assert "normal" not in result.risk_summary.lower(), (
            f"risk_summary should not describe UM as normal: {result.risk_summary}"
        )
    finally:
        if had_key is not None:
            os.environ["GROQ_API_KEY"] = had_key


def test_all_combinations(monkeypatch) -> list[str]:
    import db.database
    import db.vector_store
    monkeypatch.setattr(db.database, "save_evaluation", lambda *a, **kw: None)
    monkeypatch.setattr(db.database, "list_evaluations", lambda *a, **kw: [])
    monkeypatch.setattr(db.database, "fetchone", lambda *a, **kw: None)
    monkeypatch.setattr(db.database, "fetchall", lambda *a, **kw: [])
    monkeypatch.setattr(db.vector_store, "query_clinical_knowledge", lambda *a, **kw: [])

    import asyncio

    failures: list[str] = []
    total = 0
    passed = 0

    all_drugs = DRUG_NAMES + EXTRA_DRUGS

    for pid in PATIENT_IDS:
        for drug in all_drugs:
            total += 1
            label = f"{pid} × {drug}"
            try:
                result = asyncio.run(evaluate_prescription(pid, drug))
                if result is None:
                    failures.append(f"{label}: returned None")
                    continue
                if not result.risk_level:
                    failures.append(f"{label}: risk_level is empty/None (got {result.risk_level!r})")
                    continue
                passed += 1
            except Exception as exc:
                tb = traceback.format_exc()
                failures.append(f"{label}: raised {type(exc).__name__}: {exc}\n{tb}")

    print(f"\nResults: {passed}/{total} passed, {len(failures)} failed\n")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  • {f}")
        print()

    assert not failures, f"{len(failures)} regression(s) failed:\n" + "\n".join(failures)


if __name__ == "__main__":
    failures = test_all_combinations()
    sys.exit(1 if failures else 0)
