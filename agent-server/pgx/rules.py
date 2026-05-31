"""Deterministic pharmacogenomic rules for opioid prodrugs and CYP enzymes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from db.supabase import get_patient_by_id
from pgx.patients import PatientRecord


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CpicLevel(StrEnum):
    INFORMATIVE = "informative"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass
class DrugRule:
    name: str
    aliases: tuple[str, ...]
    pathway: str
    enzyme: str
    is_prodrug: bool
    alternatives: tuple[str, ...]
    cpic_level: CpicLevel = CpicLevel.STRONG
    cpic_note: str = "" # Fixed Bug #14: Added explicit note field


DRUG_RULES: dict[str, DrugRule] = {
    "codeine": DrugRule(
        name="Codeine",
        aliases=("codeine", "tylenol with codeine"),
        pathway="Codeine → morphine (active metabolite)",
        enzyme="CYP2D6",
        is_prodrug=True,
        alternatives=("Duloxetine", "Pregabalin"),
        cpic_level=CpicLevel.STRONG,
        cpic_note="CPIC: avoid codeine in UR and PM phenotypes."
    ),
    "tramadol": DrugRule(
        name="Tramadol",
        aliases=("tramadol", "ultram"),
        pathway="Tramadol → O-desmethyltramadol (active metabolite)",
        enzyme="CYP2D6",
        is_prodrug=True,
        alternatives=("Pregabalin", "Acetaminophen (scheduled)"),
        cpic_level=CpicLevel.STRONG,
        cpic_note="CPIC: avoid tramadol in UR and PM phenotypes."
    ),
    "hydrocodone": DrugRule(
        name="Hydrocodone",
        aliases=("hydrocodone", "vicodin", "norco"),
        pathway="Hydrocodone → hydromorphone (active metabolite)",
        enzyme="CYP2D6",
        is_prodrug=False,
        alternatives=("Pregabalin", "Duloxetine"),
        cpic_level=CpicLevel.MODERATE,
        cpic_note="CPIC: consider alternative for PM phenotypes."
    ),
    "oxycodone": DrugRule(
        name="Oxycodone",
        aliases=("oxycodone", "percocet", "oxycontin"),
        pathway="Oxycodone → oxymorphone (minor active metabolite)",
        enzyme="CYP3A4",
        is_prodrug=False,
        alternatives=("Pregabalin", "Duloxetine"),
        cpic_level=CpicLevel.MODERATE,
        cpic_note="CPIC: caution with CYP3A4 inhibitors/poor metabolizers."
    ),
    "pregabalin": DrugRule(
        name="Pregabalin",
        aliases=("pregabalin", "lyrica"),
        pathway="Pregabalin → Renal Elimination (No metabolite)",
        enzyme="—",
        is_prodrug=False,
        alternatives=(),
        cpic_level=CpicLevel.INFORMATIVE,
        cpic_note="CPIC: no PGx-based dosing changes required."
    ),
    "duloxetine": DrugRule(
        name="Duloxetine",
        aliases=("duloxetine", "cymbalta"),
        pathway="Duloxetine → 4-hydroxy duloxetine (metabolite)",
        enzyme="CYP2D6",
        is_prodrug=False,
        alternatives=("Pregabalin",),
        cpic_level=CpicLevel.MODERATE,
        cpic_note="CPIC: consider dose reduction in PM phenotypes."
    ),
    "clopidogrel": DrugRule(
        name="Clopidogrel",
        aliases=("clopidogrel", "plavix"),
        pathway="Clopidogrel → active thiol metabolite (prodrug activation)",
        enzyme="CYP2C19",
        is_prodrug=True,
        alternatives=("Prasugrel", "Ticagrelor"),
        cpic_level=CpicLevel.STRONG,
        cpic_note="CPIC: avoid in IM and PM CYP2C19 phenotypes."
    ),
}


def normalize_medication(medication: str) -> str | None:
    key = medication.strip().lower()
    for rule_key, rule in DRUG_RULES.items():
        if key == rule_key or key in rule.aliases:
            return rule_key
    return None


def get_cyp2d6_phenotype(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "CYP2D6":
            return profile["phenotype"]
    return None


def get_cyp2c19_phenotype(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "CYP2C19":
            return profile.get("phenotype")
    return None


def get_cyp3a4_note(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "CYP3A4":
            return profile.get("phenotype")
    return None


@dataclass
class RiskAssessment:
    flagged: bool
    risk_level: RiskLevel
    risk_summary: str
    pathways: list[str]
    recommended_alternative: str | None
    alternative_rationale: str
    cpic_note: str
    cpic_level: str = "informative"


def assess_prescription(
    patient_id: str,
    medication: str,
    patient: PatientRecord | None = None,
) -> RiskAssessment:
    if patient is None:
        patient = get_patient_by_id(patient_id)

    if patient is None:
        return RiskAssessment(
            flagged=True,
            risk_level=RiskLevel.HIGH,
            risk_summary=f"Unknown patient {patient_id}. Cannot verify pharmacogenomic profile.",
            pathways=[],
            recommended_alternative=None,
            alternative_rationale="Import FHIR bundle or select a seeded patient.",
            cpic_note="CPIC: verify patient identity before prescribing.",
            cpic_level=CpicLevel.INFORMATIVE.value,
        )

    drug_key = normalize_medication(medication)
    if drug_key is None:
        return RiskAssessment(
            flagged=False,
            risk_level=RiskLevel.LOW,
            risk_summary=f"{medication} is not in the demo formulary. No PGx rule triggered.",
            pathways=["Formulary lookup: no CYP2D6 prodrug rule on file"],
            recommended_alternative=None,
            alternative_rationale="Expand drug knowledge base for production.",
            cpic_note="Demo supports common pain agents: codeine, tramadol, hydrocodone, oxycodone, pregabalin, duloxetine.",
            cpic_level=CpicLevel.INFORMATIVE.value,
        )

    rule = DRUG_RULES[drug_key]
    
    # Task 3: Multi-Enzyme Cross-Talk
    # Check all available profiles against the drug rule
    phenotypes = {p["gene"]: p["phenotype"] for p in patient["cyp_profiles"]}
    
    pathways = [rule.pathway]
    cpic = rule.cpic_level.value
    alt = rule.alternatives[0] if rule.alternatives else None
    
    # Initialize multi-risk aggregation
    risks: list[tuple[RiskLevel, str]] = []

    # 1. Check Primary Enzyme (usually CYP2D6 in this ruleset)
    primary_pheno = phenotypes.get(rule.enzyme)
    if primary_pheno:
        if "Ultra-Rapid" in primary_pheno and rule.is_prodrug:
            risks.append((RiskLevel.CRITICAL, f"Ultra-rapid {rule.enzyme} metabolism leads to toxic metabolite spikes."))
        elif "Poor" in primary_pheno and rule.is_prodrug:
            risks.append((RiskLevel.HIGH, f"Poor {rule.enzyme} metabolism leads to therapeutic failure (no activation)."))
        elif "Poor" in primary_pheno and not rule.is_prodrug and rule.enzyme != "—":
            risks.append((RiskLevel.MODERATE, f"Poor {rule.enzyme} metabolism leads to increased drug exposure and toxicity risk."))

    # 2. Check Secondary Enzymes (e.g., CYP3A4 for Oxy/Hydro)
    if drug_key in ("oxycodone", "hydrocodone") and "CYP3A4" in phenotypes:
        c3a4 = phenotypes["CYP3A4"]
        if "Poor" in c3a4:
            risks.append((RiskLevel.MODERATE, "Secondary CYP3A4 pathway is impaired, reducing drug clearance."))
            pathways.append("Secondary pathway (CYP3A4) impaired")

    # 3. Handle specific drug logic (e.g., Clopidogrel)
    if drug_key == "clopidogrel" and "CYP2C19" in phenotypes:
        c2c19 = phenotypes["CYP2C19"]
        if "Poor" in c2c19 or "Intermediate" in c2c19:
            level = RiskLevel.CRITICAL if "Poor" in c2c19 else RiskLevel.HIGH
            risks.append((level, f"CYP2C19 {c2c19} phenotype: severely reduced antiplatelet activation."))

    # Aggregate Risks
    if not risks:
        # Default compatibility
        pheno_str = primary_pheno or "unknown"
        return RiskAssessment(
            flagged=False,
            risk_level=RiskLevel.NONE,
            risk_summary=f"{rule.name} is compatible with current profile ({pheno_str}).",
            pathways=pathways,
            recommended_alternative=None,
            alternative_rationale="No PGx-driven change required.",
            cpic_note=f"CPIC: standard {rule.name} dosing recommended.",
            cpic_level=cpic,
        )

    # Sort risks to find the highest
    severity_map = {RiskLevel.NONE: 0, RiskLevel.LOW: 1, RiskLevel.MODERATE: 2, RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4}
    
    # Fixed Bug #5: Guaranteed sorted_risks has at least one element due to the check above
    sorted_risks = sorted(risks, key=lambda x: severity_map[x[0]], reverse=True)
    max_risk_level, _ = sorted_risks[0]
    
    # Combine summaries
    full_summary = " | ".join([r[1] for r in sorted_risks])
    
    return RiskAssessment(
        flagged=severity_map[max_risk_level] >= 3, # Flag High and Critical
        risk_level=max_risk_level,
        risk_summary=full_summary,
        pathways=pathways,
        recommended_alternative=alt,
        alternative_rationale=f"Due to {max_risk_level.value} risk, consider switching to {alt}." if alt else "Consult specialist.",
        cpic_note=rule.cpic_note or f"CPIC: {rule.name} guidelines apply.",
        cpic_level=cpic,
    )
