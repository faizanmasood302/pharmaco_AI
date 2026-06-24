def test_review_flow_preserves_human_gate_and_unlocks_downstream_steps(
    test_client, auth_header
):
    evaluation_response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Codeine"},
        headers=auth_header,
    )
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()
    assert evaluation["evaluation_id"]
    assert evaluation["human_gate"]["status"] == "pending"
    assert len(evaluation["agent_steps"]) >= 1

    note_before_review = test_client.post(
        "/api/clinical-note",
        json=evaluation,
        headers=auth_header,
    )
    assert note_before_review.status_code == 409

    approval_response = test_client.post(
        f"/api/evaluations/{evaluation['evaluation_id']}/decision",
        json={"decision": "approved", "rationale": "Benefits documented."},
        headers=auth_header,
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()["evaluation"]
    assert approved["human_gate"]["status"] == "approved"
    assert approved["human_gate"]["reviewed_by"] == "tester@genomiclens.com"
    assert approved["human_gate"]["review_notes"] == "Benefits documented."

    note_after_approval = test_client.post(
        "/api/clinical-note",
        json=approved,
        headers=auth_header,
    )
    assert note_after_approval.status_code == 200
    assert "note" in note_after_approval.json()

    adherence_response = test_client.post(
        "/api/adherence/plans",
        json={
            "patient_id": approved["patient_id"],
            "medication": approved["medication"],
        },
        headers=auth_header,
    )
    assert adherence_response.status_code == 200
    adherence = adherence_response.json()
    assert adherence["patient_id"] == approved["patient_id"]
    assert adherence["medication"] == approved["medication"]

    rejection_response = test_client.post(
        f"/api/evaluations/{evaluation['evaluation_id']}/decision",
        json={"decision": "rejected", "rationale": "Risk exceeds benefit."},
        headers=auth_header,
    )
    assert rejection_response.status_code == 200
    rejected = rejection_response.json()["evaluation"]
    assert rejected["human_gate"]["status"] == "rejected"
    assert rejected["human_gate"]["review_notes"] == "Risk exceeds benefit."

    note_after_rejection = test_client.post(
        "/api/clinical-note",
        json=rejected,
        headers=auth_header,
    )
    assert note_after_rejection.status_code == 409
