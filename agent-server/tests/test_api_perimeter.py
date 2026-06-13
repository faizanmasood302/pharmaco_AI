def test_evaluate_requires_auth(test_client):
    """Verify that hitting the evaluation endpoint without a token returns 401."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Codeine"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_evaluate_accepts_valid_token(test_client, auth_header):
    """Verify that a valid JWT token allows access to the API."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Codeine"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_patient_not_found_returns_404(test_client, auth_header):
    """Verify that our new Typed Exception for missing patients returns a proper 404."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "NONEXISTENT", "medication": "Codeine"},
        headers=auth_header,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "PATIENT_NOT_FOUND"
    assert "request_id" in data["error"]


def test_invalid_medication_returns_200_with_warning(test_client, auth_header):
    """
    Verify that an unknown medication doesn't crash the server,
    but returns a successful response with a 'No PGx rule triggered' summary.
    """
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Windex"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert "not in the demo formulary" in response.json()["risk_summary"]
