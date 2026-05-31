from __future__ import annotations

import pytest

from agents.reporter import generate_clinical_note
from models import AgentStep, CypProfileOut, EvaluationResponse, PatientOut


def test_generate_clinical_note_fallback():
    # Mock evaluation response
    eval_resp = EvaluationResponse(
        status="success",
        patient_id="PGX-TEST",
        medication="Codeine",
        flagged=True,
        risk_level="critical",
        risk_summary="Ultra-rapid metabolizer risk",
        pathways=["CYP2D6 -> Morphine"],
        recommended_alternative="Duloxetine",
        alternative_rationale="CPIC strong recommendation",
        cpic_note="Avoid codeine",
        patient=PatientOut(
            id="PGX-TEST",
            display_name="Test Patient",
            age=45,
            sex="F",
            indication="Pain",
            cyp_profiles=[
                CypProfileOut(
                    gene="CYP2D6",
                    diplotype="*1/*1xN",
                    phenotype="Ultra-Rapid Metabolizer",
                    activity_score="2.0"
                )
            ]
        ),
        agent_steps=[
            AgentStep(agent="Research", status="complete", summary="Found patient", duration_ms=10)
        ]
    )
    
    # This should work even without Groq API key (fallback)
    note = generate_clinical_note(eval_resp)
    assert "PHARMACOGENOMIC" in note.upper()
    assert "CONSULTATION" in note.upper()
    assert "Test Patient" in note
    assert "CODEINE" in note.upper()
    assert "ULTRA-RAPID METABOLIZER" in note.upper()
    assert "DULOXETINE" in note.upper()

if __name__ == "__main__":
    pytest.main([__file__])
