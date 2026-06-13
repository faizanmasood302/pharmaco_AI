"""Minimal FHIR R4 Bundle parser for Patient + PGx Observation."""

from __future__ import annotations

import re
from typing import Any

from pgx.patients import PatientRecord

# LOINC codes for pharmacogenomic phenotype observations (demo subset)
CYP2D6_LOINC = "81236-5"
PHENOTYPE_PATTERNS = [
    (r"ultra[- ]?rapid", "Ultra-Rapid Metabolizer"),
    (r"poor", "Poor Metabolizer"),
    (r"intermediate", "Intermediate Metabolizer"),
    (r"normal", "Normal Metabolizer"),
]


def _normalize_phenotype(text: str) -> str | None:
    lower = text.lower()
    for pattern, label in PHENOTYPE_PATTERNS:
        if re.search(pattern, lower):
            return label
    return None


def _extract_patient(entry: dict[str, Any]) -> dict[str, Any] | None:
    resource = entry.get("resource", entry)
    if resource.get("resourceType") != "Patient":
        return None
    names = resource.get("name", [{}])
    given = " ".join(names[0].get("given", [])) if names else ""
    family = names[0].get("family", "") if names else ""
    display_name = f"{given} {family}".strip() or "Unknown Patient"
    birth = resource.get("birthDate", "1980-01-01")
    try:
        from datetime import date

        born = date.fromisoformat(birth[:10])
        age = (date.today() - born).days // 365
    except ValueError:
        # Fixed Bug #19: Explicit logging for failed DOB parsing
        import logging

        logging.getLogger(__name__).warning(
            "Could not parse birthDate from FHIR bundle"
        )
        age = 40
    gender = resource.get("gender", "unknown")
    sex = "M" if gender == "male" else "F" if gender == "female" else "U"
    pid = resource.get("id") or f"FHIR-{display_name.replace(' ', '-')[:12].upper()}"
    return {
        "id": pid.upper() if not pid.startswith("PGX") else pid.upper(),
        "display_name": display_name,
        "age": max(age, 1),
        "sex": sex,
        "indication": "Imported via FHIR Bundle",
    }


def _extract_observation(entry: dict[str, Any]) -> dict[str, str] | None:
    resource = entry.get("resource", entry)
    if resource.get("resourceType") != "Observation":
        return None

    code = resource.get("code", {})
    codings = code.get("coding", [])
    loinc = None
    gene = "CYP2D6"
    for c in codings:
        if c.get("system", "").endswith("loinc.org"):
            loinc = c.get("code")
        display = c.get("display", "")
        # Fixed Bug #9: Use regex to find CYP gene pattern (e.g. CYP2D6, CYP2C19)
        match = re.search(r"CYP\d[A-Z]\d+", display, re.IGNORECASE)
        if match:
            gene = match.group(0).upper()
        elif "CYP" in display.upper():
            gene = display.split()[0] if display else gene

    value_text = ""
    value_coding = resource.get("valueCodeableConcept", {})
    if value_coding:
        value_text = value_coding.get("text", "") or ""
        for c in value_coding.get("coding", []):
            value_text = value_text or c.get("display", "")

    value_string = resource.get("valueString", "")
    component_text = " ".join(
        c.get("valueCodeableConcept", {}).get("text", "")
        for c in resource.get("component", [])
    )
    combined = " ".join(
        filter(None, [value_text, value_string, component_text, code.get("text", "")])
    )

    if loinc != CYP2D6_LOINC and "CYP2D6" not in combined.upper() and "CYP" not in gene:
        return None

    phenotype = _normalize_phenotype(combined)
    if not phenotype:
        return None

    diplotype = "*1/*2"
    for ext in resource.get("extension", []):
        if "diplotype" in str(ext).lower():
            diplotype = ext.get("valueString", diplotype)

    return {
        "gene": gene if gene.startswith("CYP") else "CYP2D6",
        "diplotype": diplotype,
        "phenotype": phenotype,
        "activity_score": "imported",
    }


def _extract_medication(entry: dict[str, Any]) -> str | None:
    resource = entry.get("resource", entry)
    if resource.get("resourceType") != "MedicationRequest":
        return None

    med_cc = resource.get("medicationCodeableConcept", {})
    if med_cc:
        text = med_cc.get("text")
        if text:
            return text
        for c in med_cc.get("coding", []):
            if c.get("display"):
                return c.get("display")
    return None


def parse_fhir_bundle(bundle: dict[str, Any]) -> PatientRecord:
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("Expected FHIR Bundle resource")

    entries = bundle.get("entry", [])
    patient_data: dict[str, Any] | None = None
    cyp_profiles: list[dict[str, str]] = []
    medications: list[str] = []

    for entry in entries:
        if patient_data is None:
            patient_data = _extract_patient(entry)
        profile = _extract_observation(entry)
        if profile:
            cyp_profiles.append(profile)
        med = _extract_medication(entry)
        if med:
            medications.append(med)

    if patient_data is None:
        raise ValueError("Bundle must contain a Patient resource")

    if not cyp_profiles:
        raise ValueError("Bundle must contain a PGx Observation (CYP2D6 phenotype)")

    return {
        "id": patient_data["id"],
        "display_name": patient_data["display_name"],
        "age": patient_data["age"],
        "sex": patient_data["sex"],
        "indication": patient_data["indication"],
        "cyp_profiles": cyp_profiles,
        "current_medications": medications,
    }
