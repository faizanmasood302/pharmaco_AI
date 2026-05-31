"""Synthetic n-of-1 patient profiles for demo and boutique-clinic pilots."""

from __future__ import annotations

from typing import TypedDict


class CypProfile(TypedDict):
    gene: str
    diplotype: str
    phenotype: str
    activity_score: str


class PatientRecord(TypedDict):
    id: str
    display_name: str
    age: int
    sex: str
    indication: str
    cyp_profiles: list[CypProfile]


PATIENTS: dict[str, PatientRecord] = {
    "PGX-001": {
        "id": "PGX-001",
        "display_name": "Maria Chen",
        "age": 42,
        "sex": "F",
        "indication": "Chronic neuropathic pain (lumbar radiculopathy)",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*1xN",
                "phenotype": "Ultra-Rapid Metabolizer",
                "activity_score": "2.25 (increased)",
            },
        ],
    },
    "PGX-002": {
        "id": "PGX-002",
        "display_name": "James Okonkwo",
        "age": 58,
        "sex": "M",
        "indication": "Severe osteoarthritis (bilateral knees)",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*4/*4",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0 (no function)",
            },
        ],
    },
    "PGX-003": {
        "id": "PGX-003",
        "display_name": "Sarah Patel",
        "age": 35,
        "sex": "F",
        "indication": "Post-surgical acute pain (day 5)",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*2",
                "phenotype": "Normal Metabolizer",
                "activity_score": "1.5 (normal)",
            },
        ],
    },
}


def get_patient(patient_id: str) -> PatientRecord | None:
    return PATIENTS.get(patient_id.upper())
