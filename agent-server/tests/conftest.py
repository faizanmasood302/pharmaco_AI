import os

# Set dummy keys for testing before importing anything that might check them
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ENCRYPTION_KEY"] = "Vv_B7A-A_8yT8mZ9nN9T9mZ9nN9T9mZ9nN9T9mZ9nN8="

import pytest
from fastapi.testclient import TestClient

from auth import create_token
from main import app
from pgx.patients import PatientRecord


@pytest.fixture
def test_client():
    """Returns a FastAPI TestClient."""
    return TestClient(app)

@pytest.fixture
def auth_header():
    """Returns a valid JWT Bearer header for testing."""
    token = create_token(user_id="tester@genomiclens.com")
    return {"Authorization": f"Bearer {token}"}

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
                "activity_score": "3.0"
            }
        ]
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
                "activity_score": "0.0"
            }
        ]
    }
