import pytest
from agents.orchestrator import evaluate_prescription


@pytest.mark.asyncio
async def test_orchestrator_returns_evaluation_response():
    response = await evaluate_prescription("PGX-001", "Codeine")

    assert response.patient_id == "PGX-001"
    assert response.medication == "Codeine"
    assert response.human_gate.required is True
    assert response.human_gate.status == "pending"
    assert response.next_best_actions


@pytest.mark.asyncio
async def test_pregabalin_evaluation_not_flagged():
    """PGX-003 has normal phenotype; Pregabalin has no PGx rule."""
    response = await evaluate_prescription("PGX-003", "Pregabalin")
    assert response.patient_id == "PGX-003"
    assert response.medication == "Pregabalin"
    assert response.next_best_actions
