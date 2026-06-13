import os

# Set dummy keys for testing before importing anything that might check them
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ENCRYPTION_KEY"] = "Vv_B7A-A_8yT8mZ9nN9T9mZ9nN9T9mZ9nN9T9mZ9nN8="

import pytest
from fastapi.testclient import TestClient

from auth import verify_token
from main import app
from pgx.patients import PatientRecord


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch):
    """Keep tests deterministic and offline even when Supabase env vars are set."""
    import agents.agentic as agentic
    import db.supabase as supabase

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(agentic, "_groq", None)
    monkeypatch.setattr(supabase, "_client", None)
    monkeypatch.setattr(supabase, "_admin_client", None)
    supabase._local_evaluations.clear()
    supabase._local_plans.clear()
    supabase._local_check_ins.clear()
    supabase._local_therapy_requests.clear()
    supabase._local_therapy_candidates.clear()
    supabase._local_therapy_validation_results.clear()
    supabase._local_therapy_audit_events.clear()


@pytest.fixture
def test_client():
    """Returns a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def auth_header():
    """Returns an authenticated header while preserving real 401 tests."""
    app.dependency_overrides[verify_token] = lambda: "tester@genomiclens.com"
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def mock_ultra_rapid_patient() -> PatientRecord:
    return {
        "id": "TEST-UR",
        "display_name": "Test UR",
        "age": 30,
        "sex": "F",
        "indication": "Pain",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*1xN",
                "phenotype": "Ultra-Rapid Metabolizer",
                "activity_score": "3.0",
            }
        ],
    }


@pytest.fixture
def mock_poor_metabolizer_patient() -> PatientRecord:
    return {
        "id": "TEST-PM",
        "display_name": "Test PM",
        "age": 45,
        "sex": "M",
        "indication": "Pain",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*4/*4",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0",
            }
        ],
    }


@pytest.fixture
def eval_payload():
    """Fixture providing a standard evaluation payload for tests."""
    return {"patient_id": "PGX-001", "medication": "Codeine"}
