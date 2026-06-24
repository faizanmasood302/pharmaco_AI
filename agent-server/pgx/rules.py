"""Deterministic pharmacogenomic rules for drug-gene interactions.

Drug rules are loaded from structured JSON seed files, validated against
a Pydantic schema at load time, and cached in the DRUG_RULES dict.
Fails closed on invalid seed data — the server will not start with
a malformed entry.

RxNorm enrichment: when local fuzzy matching fails, normalize_medication
may consult the NIH RxNorm API (free, no key required) to resolve brand
names to canonical ingredient names. This is an enrichment layer — the
system works correctly without it when RxNorm is unreachable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from db.database import get_patient_by_id
from pgx.patients import PatientRecord
from pgx.seed.schema import DrugSeedData, DrugRuleEntry

logger = logging.getLogger(__name__)


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CpicLevel(StrEnum):
    INFORMATIVE = "informative"
    OPTIONAL = "optional"
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
    cpic_note: str = ""
    um_consider_alternative: bool = False
    rule_version: str = "1.0.0"
    cpic_guideline: str = ""
    source_citation: str = ""
    last_reviewed_date: str = ""


# ---------------------------------------------------------------------------
# Seed loader — validates against Pydantic schema, fails closed on mismatch
# ---------------------------------------------------------------------------

_SEED_DIR = Path(__file__).resolve().parent / "seed"


def _load_drug_rules() -> dict[str, DrugRule]:
    path = _SEED_DIR / "drugs.json"
    if not path.exists():
        logger.error("Drug seed file not found: %s", path)
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = DrugSeedData(**raw)

    cpic_map = {
        "strong": CpicLevel.STRONG,
        "moderate": CpicLevel.MODERATE,
        "optional": CpicLevel.OPTIONAL,
        "informative": CpicLevel.INFORMATIVE,
    }

    rules: dict[str, DrugRule] = {}
    for key, entry in validated.rules.items():
        rules[key] = DrugRule(
            name=entry.name,
            aliases=tuple(entry.aliases),
            pathway=entry.pathway,
            enzyme=entry.enzyme,
            is_prodrug=entry.is_prodrug,
            alternatives=tuple(entry.alternatives),
            cpic_level=cpic_map.get(entry.cpic_level, CpicLevel.INFORMATIVE),
            cpic_note=entry.cpic_note,
            um_consider_alternative=entry.um_consider_alternative,
            rule_version=entry.rule_version,
            cpic_guideline=entry.cpic_guideline,
            source_citation=entry.source_citation,
            last_reviewed_date=entry.last_reviewed_date,
        )

    logger.info("Loaded %d drug rules from %s", len(rules), path.name)
    return rules


# ---------------------------------------------------------------------------
# RxNorm enrichment — NIH API, no key required
# ---------------------------------------------------------------------------

_RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
_RXNORM_TIMEOUT = 3  # seconds


def rxnorm_lookup(name: str) -> str | None:
    """Resolve a drug name to its RxNorm canonical ingredient name.

    Returns the canonical name (lowercased) if found, None otherwise.
    This is an enrichment layer — the system works without it.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    try:
        quoted = urllib.parse.quote(name)
        url = f"{_RXNORM_BASE}/rxcui.json?name={quoted}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_RXNORM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())

        id_group = data.get("idGroup", {})
        rxcuis = id_group.get("rxnormId", [])
        if not rxcuis:
            logger.debug("RxNorm: no RxCUI found for '%s'", name)
            return None
        rxcui = rxcuis[0]

        # Get canonical name for the RxCUI
        url = f"{_RXNORM_BASE}/rxcui/{rxcui}/name.json"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_RXNORM_TIMEOUT) as resp:
            name_data = json.loads(resp.read().decode())

        canonical = name_data.get("name", "").lower().strip()
        if canonical:
            logger.debug("RxNorm: '%s' -> '%s' (rxcui=%s)", name, canonical, rxcui)
            return canonical
        return None

    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError, KeyError) as exc:
        logger.debug("RxNorm lookup failed for '%s': %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# Module-level cache — populated at import time
# ---------------------------------------------------------------------------

DRUG_RULES: dict[str, DrugRule] = _load_drug_rules()


# ---------------------------------------------------------------------------
# API functions — see docstrings for contract
# ---------------------------------------------------------------------------


def normalize_medication(medication: str) -> str | None:
    """Map a medication string to a canonical drug key in DRUG_RULES.

    Resolution order:
      1. Local fuzzy matching against DRUG_RULES keys and aliases
         (always works, no external dependencies).
      2. RxNorm API enrichment when local matching fails
         (gracefully degrades when RxNorm is unreachable).

    Returns the canonical drug key (e.g. 'codeine') or None if unresolvable.
    """
    key = medication.strip().lower()

    # Step 1: local fuzzy matching (fast, deterministic, no external deps)
    for rule_key, rule in DRUG_RULES.items():
        if key == rule_key or key in rule.aliases:
            return rule_key

    # Step 2: RxNorm enrichment (external API, may fail)
    try:
        canonical = rxnorm_lookup(key)
        if canonical:
            for rule_key, rule in DRUG_RULES.items():
                if canonical == rule_key or canonical in rule.aliases:
                    return rule_key
            # Drug recognized by RxNorm but not in our curated rules
            logger.debug(
                "RxNorm recognized '%s' -> '%s', but drug not in DRUG_RULES",
                medication,
                canonical,
            )
    except Exception as exc:
        logger.debug("RxNorm enrichment skipped for '%s': %s", medication, exc)

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


def get_slco1b1_phenotype(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "SLCO1B1":
            return profile.get("phenotype")
    return None


def get_abcg2_phenotype(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "ABCG2":
            return profile.get("phenotype")
    return None


def get_cyp2c9_phenotype(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "CYP2C9":
            return profile.get("phenotype")
    return None


def get_cyp3a4_note(patient: PatientRecord) -> str | None:
    for profile in patient["cyp_profiles"]:
        if profile["gene"] == "CYP3A4":
            return profile.get("phenotype")
    return None


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


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
            cpic_note="Demo formulary: codeine, tramadol, hydrocodone, oxycodone, pregabalin, duloxetine, clopidogrel, citalopram, escitalopram, sertraline, paroxetine, simvastatin, atorvastatin, rosuvastatin, fluvastatin.",
            cpic_level=CpicLevel.INFORMATIVE.value,
        )

    rule = DRUG_RULES[drug_key]

    # Multi-Enzyme Cross-Talk: check all available profiles against the drug rule
    phenotypes = {p["gene"]: p["phenotype"] for p in patient["cyp_profiles"]}

    pathways = [rule.pathway]
    cpic = rule.cpic_level.value
    alt = rule.alternatives[0] if rule.alternatives else None

    # Initialize multi-risk aggregation
    risks: list[tuple[RiskLevel, str]] = []

    # 1. Check Primary Enzyme
    primary_pheno = phenotypes.get(rule.enzyme)
    if primary_pheno:
        if "Ultra-Rapid" in primary_pheno and rule.is_prodrug:
            risks.append(
                (
                    RiskLevel.CRITICAL,
                    f"Ultra-rapid {rule.enzyme} metabolism leads to toxic metabolite spikes.",
                )
            )
        elif "Poor" in primary_pheno and rule.is_prodrug:
            risks.append(
                (
                    RiskLevel.HIGH,
                    f"Poor {rule.enzyme} metabolism leads to therapeutic failure (no activation).",
                )
            )
        elif "Poor" in primary_pheno and not rule.is_prodrug and rule.enzyme != "\u2014":
            risks.append(
                (
                    RiskLevel.MODERATE,
                    f"Poor {rule.enzyme} metabolism leads to increased drug exposure and toxicity risk.",
                )
            )
        elif "Ultra-Rapid" in primary_pheno and not rule.is_prodrug and rule.um_consider_alternative:
            risks.append(
                (
                    RiskLevel.MODERATE,
                    f"Ultra-rapid {rule.enzyme} metabolism may reduce efficacy; consider alternative per CPIC.",
                )
            )

    # 2. Check Secondary Enzymes (e.g., CYP3A4 for Oxy/Hydro)
    if drug_key in ("oxycodone", "hydrocodone") and "CYP3A4" in phenotypes:
        c3a4 = phenotypes["CYP3A4"]
        if "Poor" in c3a4:
            risks.append(
                (
                    RiskLevel.MODERATE,
                    "Secondary CYP3A4 pathway is impaired, reducing drug clearance.",
                )
            )
            pathways.append("Secondary pathway (CYP3A4) impaired")

    # 3. Handle specific drug logic (e.g., Clopidogrel)
    if drug_key == "clopidogrel" and "CYP2C19" in phenotypes:
        c2c19 = phenotypes["CYP2C19"]
        if "Poor" in c2c19 or "Intermediate" in c2c19:
            level = RiskLevel.CRITICAL if "Poor" in c2c19 else RiskLevel.HIGH
            risks.append(
                (
                    level,
                    f"CYP2C19 {c2c19} phenotype: severely reduced antiplatelet activation.",
                )
            )

    # 4. Statin-specific logic (SLCO1B1, ABCG2, CYP2C9)
    slco1b1 = phenotypes.get("SLCO1B1")
    abcg2 = phenotypes.get("ABCG2")
    cyp2c9 = phenotypes.get("CYP2C9")

    if drug_key == "simvastatin":
        if slco1b1 and "Poor" in slco1b1:
            risks.append((RiskLevel.CRITICAL, f"SLCO1B1 {slco1b1}: highly increased myopathy risk with simvastatin. CPIC: prescribe alternative statin (Table 2)."))
        elif slco1b1 and "Decreased" in slco1b1:
            risks.append((RiskLevel.HIGH, f"SLCO1B1 {slco1b1}: increased myopathy risk. CPIC: limit dose to <20 mg/day or prescribe alternative statin (Table 2)."))

    elif drug_key == "atorvastatin":
        if slco1b1 and "Poor" in slco1b1:
            risks.append((RiskLevel.HIGH, f"SLCO1B1 {slco1b1}: increased atorvastatin exposure. CPIC: starting dose ≤20 mg. If >20 mg needed, consider rosuvastatin or combination therapy (Table 2)."))
        elif slco1b1 and "Decreased" in slco1b1:
            risks.append((RiskLevel.MODERATE, f"SLCO1B1 {slco1b1}: increased atorvastatin exposure. CPIC: starting dose ≤40 mg. Aware of increased myopathy risk at 40 mg (Table 2)."))

    elif drug_key == "rosuvastatin":
        rosuvastatin_risks = []
        if slco1b1 and "Poor" in slco1b1:
            rosuvastatin_risks.append("SLCO1B1 Poor")
        if abcg2 and "Poor" in abcg2:
            rosuvastatin_risks.append("ABCG2 Poor")
        if slco1b1 and "Decreased" in slco1b1:
            rosuvastatin_risks.append("SLCO1B1 Decreased")

        if "SLCO1B1 Poor" in rosuvastatin_risks and "ABCG2 Poor" in rosuvastatin_risks:
            risks.append((RiskLevel.MODERATE, "SLCO1B1 Poor + ABCG2 Poor: CPIC recommends starting dose ≤10 mg. If >10 mg needed, consider alternative statin or combination therapy (Table 5)."))
        elif "SLCO1B1 Poor" in rosuvastatin_risks:
            risks.append((RiskLevel.MODERATE, "SLCO1B1 Poor: CPIC recommends starting dose ≤20 mg. If >20 mg needed, consider combination therapy (Table 2)."))
        elif "ABCG2 Poor" in rosuvastatin_risks:
            risks.append((RiskLevel.MODERATE, "ABCG2 Poor: increased rosuvastatin exposure (AUC +144%). CPIC: starting dose ≤20 mg (Table 3)."))
        elif "SLCO1B1 Decreased" in rosuvastatin_risks:
            risks.append((RiskLevel.MODERATE, "SLCO1B1 Decreased: aware of increased myopathy risk for doses >20 mg (Table 2)."))

    elif drug_key == "fluvastatin":
        if cyp2c9 and "Poor" in cyp2c9:
            risks.append((RiskLevel.HIGH, f"CYP2C9 {cyp2c9}: increased fluvastatin exposure. CPIC: starting dose ≤20 mg/day. If >20 mg needed, consider alternative statin or combination therapy (Table 4)."))
        elif cyp2c9 and "Intermediate" in cyp2c9:
            risks.append((RiskLevel.MODERATE, f"CYP2C9 {cyp2c9}: increased fluvastatin exposure. CPIC: avoid doses >40 mg/day. Consider alternative statin if higher potency needed (Table 4)."))
        if slco1b1 and "Poor" in slco1b1:
            risks.append((RiskLevel.MODERATE, f"SLCO1B1 {slco1b1}: CPIC recommends starting dose ≤40 mg/day. Aware of increased myopathy risk >40 mg (Table 2)."))

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
    severity_map = {
        RiskLevel.NONE: 0,
        RiskLevel.LOW: 1,
        RiskLevel.MODERATE: 2,
        RiskLevel.HIGH: 3,
        RiskLevel.CRITICAL: 4,
    }

    sorted_risks = sorted(risks, key=lambda x: severity_map[x[0]], reverse=True)
    max_risk_level, _ = sorted_risks[0]

    # Combine summaries
    full_summary = " | ".join([r[1] for r in sorted_risks])

    return RiskAssessment(
        flagged=severity_map[max_risk_level] >= 3,  # Flag High and Critical
        risk_level=max_risk_level,
        risk_summary=full_summary,
        pathways=pathways,
        recommended_alternative=alt,
        alternative_rationale=f"Due to {max_risk_level.value} risk, consider switching to {alt}."
        if alt
        else "Consult specialist.",
        cpic_note=rule.cpic_note or f"CPIC: {rule.name} guidelines apply.",
        cpic_level=cpic,
    )
