import uuid


def test_therapy_graph_revision_loop():
    from agents.therapy_orchestrator import orchestrate_therapy_generation

    # Run with max_iterations=2 to see it complete successfully
    response = orchestrate_therapy_generation("PGX-001", "opioid research", max_iterations=2)

    assert response.status == "research_review_required"
    assert response.target_disease == "opioid research"
    assert len(response.agent_steps) > 0
    assert response.final_candidate is not None


def test_therapy_decision_persistence(test_client, auth_header):
    # 1. Generate a therapy
    gen_res = test_client.post(
        "/api/generate-therapy",
        json={
            "patient_id": "PGX-001",
            "target_disease": "decision test",
            "max_iterations": 3,
        },
        headers=auth_header,
    )
    assert gen_res.status_code == 200
    data = gen_res.json()
    req_id = data["therapy_request_id"]

    # 2. Submit a decision
    dec_res = test_client.post(
        f"/api/therapy-requests/{req_id}/decision",
        json={
            "decision": "approved",
            "rationale": "Looks good for research.",
            "reviewer": "Dr. Test",
        },
        headers=auth_header,
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["decision"] == "approved"
    assert dec_data["result"]["human_gate"]["status"] == "approved"


def test_therapy_decision_not_found(test_client, auth_header):
    dec_res = test_client.post(
        "/api/therapy-requests/non-existent-id/decision",
        json={
            "decision": "approved",
            "rationale": "Looks good for research.",
            "reviewer": "Dr. Test",
        },
        headers=auth_header,
    )
    assert dec_res.status_code == 404
