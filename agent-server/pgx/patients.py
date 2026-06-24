"""Synthetic n-of-1 patient profiles for demo and boutique-clinic pilots."""

from __future__ import annotations

from typing import TypedDict


class CypProfile(TypedDict):
    gene: str
    diplotype: str
    phenotype: str
    activity_score: str


class PatientRecord(TypedDict, total=False):
    id: str
    display_name: str
    age: int
    sex: str
    indication: str
    cyp_profiles: list[CypProfile]
    current_medications: list[str]


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
    "PGX-004": {
        "id": "PGX-004",
        "display_name": "Muhammad Faizan",
        "age": 36,
        "sex": "M",
        "indication": "Severe acute pain post-injury",
        "cyp_profiles": [
            {
                "gene": "CYP2D6",
                "diplotype": "*1/*1xN",
                "phenotype": "Ultra-Rapid Metabolizer",
                "activity_score": "2.25 (increased)",
            },
        ],
    },
    "PGX-005": {
        "id": "PGX-005",
        "display_name": "Wei Zhang",
        "age": 45,
        "sex": "M",
        "indication": "Generalized anxiety disorder (GAD)",
        "cyp_profiles": [
            {
                "gene": "CYP2C19",
                "diplotype": "*2/*3",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0 (no function)",
            },
        ],
    },
    "PGX-006": {
        "id": "PGX-006",
        "display_name": "Amara Okafor",
        "age": 34,
        "sex": "F",
        "indication": "Major depressive disorder (MDD)",
        "cyp_profiles": [
            {
                "gene": "CYP2C19",
                "diplotype": "*1/*2",
                "phenotype": "Intermediate Metabolizer",
                "activity_score": "1.0 (reduced)",
            },
            {
                "gene": "CYP2D6",
                "diplotype": "*4/*4",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0 (no function)",
            },
        ],
    },
    "PGX-007": {
        "id": "PGX-007",
        "display_name": "Robert Kim",
        "age": 55,
        "sex": "M",
        "indication": "Primary hyperlipidemia, LDL-C 190 mg/dL",
        "cyp_profiles": [
            {
                "gene": "SLCO1B1",
                "diplotype": "*5/*5",
                "phenotype": "Poor Function",
                "activity_score": "0.0 (no function)",
            },
            {
                "gene": "CYP2C9",
                "diplotype": "*1/*1",
                "phenotype": "Normal Metabolizer",
                "activity_score": "2.0 (normal)",
            },
        ],
    },
    "PGX-008": {
        "id": "PGX-008",
        "display_name": "Priya Sharma",
        "age": 62,
        "sex": "F",
        "indication": "ASCVD, post-MI, LDL-C 160 mg/dL on lifestyle modification",
        "cyp_profiles": [
            {
                "gene": "SLCO1B1",
                "diplotype": "*1/*1",
                "phenotype": "Normal Function",
                "activity_score": "1.0 (normal)",
            },
            {
                "gene": "ABCG2",
                "diplotype": "c.421 A/A",
                "phenotype": "Poor Function",
                "activity_score": "0.0 (reduced expression)",
            },
        ],
    },
    "PGX-009": {
        "id": "PGX-009",
        "display_name": "Carlos Mendez",
        "age": 48,
        "sex": "M",
        "indication": "Mixed dyslipidemia, diabetes type 2",
        "cyp_profiles": [
            {
                "gene": "SLCO1B1",
                "diplotype": "*1/*5",
                "phenotype": "Decreased Function",
                "activity_score": "0.5 (reduced)",
            },
            {
                "gene": "CYP2C9",
                "diplotype": "*3/*3",
                "phenotype": "Poor Metabolizer",
                "activity_score": "0.0 (no function)",
            },
        ],
    },
}


def get_patient(patient_id: str) -> PatientRecord | None:
    return PATIENTS.get(patient_id.upper())


def extract_phenotype(patient_data: str) -> str:
    """Extract CYP phenotype from a patient data string.
    
    Guaranteed to return lowercase: returns one of
    'ultra-rapid metabolizer', 'poor metabolizer',
    'normal metabolizer', 'intermediate metabolizer'.
    Defaults to 'normal metabolizer' if no match found.
    
    All callers may safely rely on the lowercase contract
    without applying .lower() themselves.
    """
    import re
    match = re.search(r"(ultra-rapid|poor|normal|intermediate)\s*metabolizer", patient_data, re.IGNORECASE)
    if match:
        return match.group(0).lower()
    return "normal metabolizer"
