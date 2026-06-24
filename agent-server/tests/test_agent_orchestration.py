import pytest
from agents.orchestrator import evaluate_prescription


@pytest.mark.asyncio
async def test_evaluate_prescription_returns_evaluation_response():
    """Verify that the evaluation response contains required fields."""
    res = await evaluate_prescription("PGX-001", "Codeine")
    assert res.flagged is not None
    assert res.risk_level in ("low", "moderate", "high", "critical")
    assert res.patient_id == "PGX-001"
    assert res.medication == "Codeine"


@pytest.mark.asyncio
async def test_logic_tree_is_present():
    """Verify that the final evaluation response contains a structured logic tree."""
    res = await evaluate_prescription("PGX-001", "Codeine")
    assert "logic_tree" in res.model_dump()
    assert len(res.logic_tree["children"]) > 0


@pytest.mark.asyncio
async def test_human_gate_always_required():
    """Verify that every evaluation requires human review."""
    res = await evaluate_prescription("PGX-001", "Codeine")
    assert res.human_gate.required is True
    assert res.human_gate.status == "pending"


@pytest.mark.asyncio
async def test_evaluate_prescription_includes_patient_profile():
    """Verify patient profile is included in evaluation response."""
    res = await evaluate_prescription("PGX-001", "Codeine")
    assert res.patient is not None
    assert res.patient.id == "PGX-001"
    assert "pain" in res.patient.indication.lower()
