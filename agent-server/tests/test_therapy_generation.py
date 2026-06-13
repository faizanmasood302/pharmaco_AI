from agents.therapy_orchestrator import orchestrate_therapy_generation
from agents.validation import validate_research_mrna_candidate
from db.supabase import get_therapy_request_by_id


def test_therapy_generation_graph_returns_research_review_packet():
    response = orchestrate_therapy_generation(
        "PGX-001",
        "opioid pain response research",
        max_iterations=3,
    )

    assert response.status == "research_review_required"
    assert response.final_candidate is not None
    assert response.validation_result is not None
    assert response.validation_result.passed is True
    assert response.evidence_bundle is not None
    assert response.evidence_sources
    assert response.human_gate.required is True
    assert response.human_gate.status == "pending"
    assert response.candidate_history
    assert any(step.agent == "DiseaseTargetRAG" for step in response.agent_steps)
    assert any(step.agent == "InSilicoValidation" for step in response.agent_steps)
    assert any("Research simulation only" in note for note in response.safety_notes)


def test_generate_therapy_api_preserves_existing_route(test_client, auth_header):
    response = test_client.post(
        "/api/generate-therapy",
        json={
            "patient_id": "PGX-001",
            "target_disease": "opioid pain response research",
            "max_iterations": 3,
        },
        headers=auth_header,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "research_review_required"
    assert data["mrna_sequence"].startswith("AUG")
    assert data["validation_result"]["passed"] is True
    assert data["human_gate"]["status"] == "pending"
    assert data["evidence_sources"]

    saved = get_therapy_request_by_id(data["therapy_request_id"])
    assert saved is not None
    assert saved["patient_id"] == "PGX-001"
    assert saved["target_disease"] == "opioid pain response research"
    assert saved["candidate_history"]
    assert saved["validation_result"]["passed"] is True
    assert saved["audit_trail"]


def test_research_mrna_validator_blocks_internal_stop_codons():
    validation, _elapsed = validate_research_mrna_candidate("AUGGCUUAAUGGUAA")

    assert validation["passed"] is False
    assert any(
        "internal stop" in reason.lower() for reason in validation["blocked_reasons"]
    )
    assert any("internal stop" in hint.lower() for hint in validation["revision_hints"])
