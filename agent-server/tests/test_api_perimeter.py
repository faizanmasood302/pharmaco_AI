def test_evaluate_requires_auth(test_client):
    """Verify that hitting the evaluation endpoint without a token is rejected."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Codeine"},
    )
    # HTTPBearer raises 403 when Authorization header is missing
    assert response.status_code in (401, 403)


def test_evaluate_accepts_valid_token(test_client, auth_header):
    """Verify that a valid JWT token allows access to the API."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Codeine"},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_unknown_patient_returns_200(test_client, auth_header):
    """Verify that unknown patient ID returns 200 with fallback."""
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "NONEXISTENT", "medication": "Codeine"},
        headers=auth_header,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_invalid_medication_returns_200(test_client, auth_header):
    """
    Verify that an unknown medication doesn't crash the server,
    but returns a successful response.
    """
    response = test_client.post(
        "/api/evaluate-prescription",
        json={"patient_id": "PGX-001", "medication": "Windex"},
        headers=auth_header,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
