from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from agents.knowledge import retrieve_clinical_evidence
from agents.tools import execute_tool
from agents.tracing import get_drift_monitor, traceable
from config import GROQ_MODEL
from models import AdjudicatorOutput, SpecialistOpinion

logger = logging.getLogger(__name__)

try:
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


RISK_SEVERITY = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}


def _groq_json(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 300,
    temperature: float = 0.2,
) -> dict[str, Any] | None:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        return None
    try:
        completion = _groq.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as exc:
        logger.warning("Debate LLM call failed: %s", exc)
        return None


# --- Specialist Agents ---


def _pharmacologist_fallback(
    medication: str, phenotype: str, evidence_text: str | None
) -> SpecialistOpinion:
    drug_info = execute_tool("query_drug_db", {"medication": medication})
    evidence_lower = (evidence_text or "").lower()

    if "not found" in drug_info.lower():
        return SpecialistOpinion(
            agent_name="Pharmacologist",
            risk_level="low",
            flagged=False,
            risk_summary=f"{medication} is not in the demo formulary. No pharmacologic PGx rule applies.",
            recommendation=None,
            reasoning=drug_info,
            confidence=0.55,
            evidence_refs=[],
        )

    is_prodrug = "is prodrug: true" in drug_info.lower()
    phenotype_lower = phenotype.lower()

    if is_prodrug:
        if "ultra-rapid" in phenotype_lower:
            return SpecialistOpinion(
                agent_name="Pharmacologist",
                risk_level="critical",
                flagged=True,
                risk_summary=f"Ultra-rapid metabolism + prodrug ({medication}) creates toxicity risk from excessive active metabolite formation.",
                recommendation="Duloxetine",
                reasoning=drug_info,
                confidence=0.94,
                evidence_refs=["drug_db"],
            )
        if "poor" in phenotype_lower:
            return SpecialistOpinion(
                agent_name="Pharmacologist",
                risk_level="high",
                flagged=True,
                risk_summary=f"Poor metabolism + prodrug ({medication}) leads to inadequate activation and therapeutic failure.",
                recommendation="Pregabalin",
                reasoning=drug_info,
                confidence=0.91,
                evidence_refs=["drug_db"],
            )

    if any(term in evidence_lower for term in ("avoid", "caution", "contraindicated")):
        return SpecialistOpinion(
            agent_name="Pharmacologist",
            risk_level="moderate",
            flagged=True,
            risk_summary=f"Evidence flags caution for {medication} in {phenotype} phenotype.",
            recommendation=None,
            reasoning=evidence_text or drug_info,
            confidence=0.72,
            evidence_refs=["retrieved_evidence"],
        )

    return SpecialistOpinion(
        agent_name="Pharmacologist",
        risk_level="low",
        flagged=False,
        risk_summary=f"{medication} is pharmacologically compatible with {phenotype} profile.",
        recommendation=None,
        reasoning=drug_info,
        confidence=0.78,
        evidence_refs=["drug_db"],
    )


def _pharmacologist_agent(
    medication: str,
    phenotype: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> SpecialistOpinion:
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a pharmacologist agent specializing in drug metabolism and pharmacokinetics. "
                "Analyze the medication, patient phenotype, and evidence. "
                "Return strict JSON with keys: risk_level, flagged, risk_summary, recommendation, "
                "reasoning, confidence, evidence_refs. "
                "Focus on enzyme pathways, prodrug activation, and drug-drug interaction potential."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "medication": medication,
                    "phenotype": phenotype,
                    "evidence_sources": evidence_sources,
                    "evidence_text": evidence_text or "No source-backed evidence retrieved.",
                },
                indent=2,
            ),
        },
    ]

    raw = _groq_json(prompt, max_tokens=320, temperature=0.15)
    if raw is not None:
        try:
            return SpecialistOpinion(agent_name="Pharmacologist", **raw)
        except Exception as exc:
            logger.warning("Failed to parse pharmacologist JSON: %s", exc)

    return _pharmacologist_fallback(medication, phenotype, evidence_text)


def _geneticist_fallback(
    phenotype: str, evidence_text: str | None
) -> SpecialistOpinion:
    pheno_info = execute_tool("get_phenotype_info", {"phenotype": phenotype})
    evidence_lower = (evidence_text or "").lower()
    prodrug_mentioned = any(
        term in evidence_lower for term in ("prodrug", "activation", "codeine", "tramadol", "clopidogrel")
    )
    caution_mentioned = any(
        term in evidence_lower for term in ("avoid", "contraindicated", "critical")
    )

    phenotype_lower = phenotype.lower()

    if "ultra-rapid" in phenotype_lower and prodrug_mentioned:
        return SpecialistOpinion(
            agent_name="Geneticist",
            risk_level="high",
            flagged=True,
            risk_summary=f"{phenotype}: increased activity. When combined with a prodrug, toxicity risk is elevated.",
            recommendation="Consider non-prodrug alternatives.",
            reasoning=pheno_info,
            confidence=0.90,
            evidence_refs=["phenotype_db"],
        )

    if "poor" in phenotype_lower and prodrug_mentioned:
        return SpecialistOpinion(
            agent_name="Geneticist",
            risk_level="high",
            flagged=True,
            risk_summary=f"{phenotype}: reduced activity. Prodrug activation will be impaired.",
            recommendation="Use non-prodrug alternatives.",
            reasoning=pheno_info,
            confidence=0.89,
            evidence_refs=["phenotype_db"],
        )

    if "ultra-rapid" in phenotype_lower:
        return SpecialistOpinion(
            agent_name="Geneticist",
            risk_level="low",
            flagged=False,
            risk_summary=f"{phenotype}: increased activity noted. Medication does not appear to be a prodrug requiring this enzyme.",
            recommendation=None,
            reasoning=pheno_info,
            confidence=0.75,
            evidence_refs=["phenotype_db"],
        )

    if "poor" in phenotype_lower:
        return SpecialistOpinion(
            agent_name="Geneticist",
            risk_level="low",
            flagged=False,
            risk_summary=f"{phenotype}: reduced activity noted. Medication does not appear to depend on this enzyme for activation.",
            recommendation=None,
            reasoning=pheno_info,
            confidence=0.75,
            evidence_refs=["phenotype_db"],
        )

    if "intermediate" in phenotype_lower:
        return SpecialistOpinion(
            agent_name="Geneticist",
            risk_level="moderate" if caution_mentioned else "low",
            flagged=caution_mentioned,
            risk_summary=f"{phenotype}: moderately reduced activity."
            if not caution_mentioned
            else f"{phenotype}: evidence suggests caution.",
            recommendation=None,
            reasoning=pheno_info,
            confidence=0.75,
            evidence_refs=["phenotype_db"],
        )

    return SpecialistOpinion(
        agent_name="Geneticist",
        risk_level="none",
        flagged=False,
        risk_summary=f"{phenotype}: standard enzymatic activity. No genetic contraindication.",
        recommendation=None,
        reasoning=pheno_info,
        confidence=0.85,
        evidence_refs=["phenotype_db"],
    )


def _geneticist_agent(
    phenotype: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> SpecialistOpinion:
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a clinical geneticist agent specializing in pharmacogenomic variant interpretation. "
                "Analyze the patient's CYP phenotype and the clinical evidence. "
                "Return strict JSON with keys: risk_level, flagged, risk_summary, recommendation, "
                "reasoning, confidence, evidence_refs. "
                "Focus on genotype-phenotype correlation, allele function, and evidence-based phenotype interpretation."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phenotype": phenotype,
                    "evidence_sources": evidence_sources,
                    "evidence_text": evidence_text or "No source-backed evidence retrieved.",
                },
                indent=2,
            ),
        },
    ]

    raw = _groq_json(prompt, max_tokens=320, temperature=0.15)
    if raw is not None:
        try:
            return SpecialistOpinion(agent_name="Geneticist", **raw)
        except Exception as exc:
            logger.warning("Failed to parse geneticist JSON: %s", exc)

    return _geneticist_fallback(phenotype, evidence_text)


def _clinician_fallback(
    patient: dict[str, Any],
    medication: str,
    evidence_text: str | None,
) -> SpecialistOpinion:
    evidence_lower = (evidence_text or "").lower()
    indication = patient.get("indication", "").lower()
    age = patient.get("age", 0)
    med_lower = medication.lower()

    medication_specific_concern = any(
        med_lower in evidence_lower and term in evidence_lower
        for term in ("avoid", "contraindicated", "critical", "hard stop")
    )

    if medication_specific_concern:
        return SpecialistOpinion(
            agent_name="Clinician",
            risk_level="moderate",
            flagged=True,
            risk_summary=f"Evidence directly flags a concern about {medication} that warrants clinical review.",
            recommendation=None,
            reasoning=f"Contraindication terms found in evidence mentioning {medication}.",
            confidence=0.72,
            evidence_refs=["patient_profile", "retrieved_evidence"],
        )

    general_caution = any(
        term in evidence_lower for term in ("avoid", "critical", "contraindicated")
    )
    if general_caution:
        return SpecialistOpinion(
            agent_name="Clinician",
            risk_level="low",
            flagged=False,
            risk_summary=f"Evidence contains general cautions not specific to {medication}. Standard review applies.",
            recommendation=None,
            reasoning=f"General caution indicators found, but not specific to {medication}.",
            confidence=0.78,
            evidence_refs=["patient_profile", "retrieved_evidence"],
        )

    if "pain" in indication and age and age < 18:
        return SpecialistOpinion(
            agent_name="Clinician",
            risk_level="low",
            flagged=False,
            risk_summary=f"Pediatric patient ({age}) — standard pediatric precautions apply.",
            recommendation=None,
            reasoning=f"Age {age} requires weight-based dosing but no PGx-specific concern beyond evidence.",
            confidence=0.75,
            evidence_refs=["patient_profile"],
        )

    return SpecialistOpinion(
        agent_name="Clinician",
        risk_level="none",
        flagged=False,
        risk_summary=f"No additional clinical concerns for {medication} beyond the pharmacogenomic evidence.",
        recommendation=None,
        reasoning=f"Patient age {age}, indication '{indication}'. Standard monitoring recommended.",
        confidence=0.85,
        evidence_refs=["patient_profile"],
    )


def _clinician_agent(
    patient: dict[str, Any],
    medication: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> SpecialistOpinion:
    profile = {
        "age": patient.get("age", "N/A"),
        "sex": patient.get("sex", "U"),
        "indication": patient.get("indication", "Unknown"),
        "medication": medication,
    }

    prompt = [
        {
            "role": "system",
            "content": (
                "You are a primary care clinician agent. "
                "Review the patient profile, medication, and pharmacogenomic evidence through a clinical lens. "
                "Return strict JSON with keys: risk_level, flagged, risk_summary, recommendation, "
                "reasoning, confidence, evidence_refs. "
                "Consider age, sex, indication, polypharmacy risk, and clinical context."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient_profile": profile,
                    "medication": medication,
                    "evidence_sources": evidence_sources,
                    "evidence_text": evidence_text or "No source-backed evidence retrieved.",
                },
                indent=2,
            ),
        },
    ]

    raw = _groq_json(prompt, max_tokens=320, temperature=0.15)
    if raw is not None:
        try:
            return SpecialistOpinion(agent_name="Clinician", **raw)
        except Exception as exc:
            logger.warning("Failed to parse clinician JSON: %s", exc)

    return _clinician_fallback(patient, medication, evidence_text)


# --- Adjudicator ---


def _adjudicator_fallback(opinions: list[SpecialistOpinion]) -> AdjudicatorOutput:
    risk_levels = [o.risk_level for o in opinions]
    severities = [RISK_SEVERITY.get(r, 0) for r in risk_levels]
    max_sev = max(severities)
    highest_risk = [k for k, v in RISK_SEVERITY.items() if v == max_sev][0]

    flagged_count = sum(1 for o in opinions if o.flagged)
    majority_flagged = flagged_count > len(opinions) / 2

    unanimous = len(set(risk_levels)) == 1
    sev_counts = {s: severities.count(s) for s in set(severities)}
    majority_sev = max(sev_counts, key=sev_counts.get)
    majority_risk = [k for k, v in RISK_SEVERITY.items() if v == majority_sev][0]
    agreement = "unanimous" if unanimous else "majority"

    consensus_summary = (
        f"Panel of {len(opinions)} specialists reviewed the case. "
        f"Risk levels: {', '.join(risk_levels)}. "
        f"Consensus: {agreement} agreement on {highest_risk} risk."
    )

    recommendations = [o.recommendation for o in opinions if o.recommendation]
    top_rec = recommendations[0] if recommendations else None

    confidences = [o.confidence for o in opinions]
    avg_confidence = round(sum(confidences) / len(confidences), 2)

    if top_rec:
        alt_ratio = (
            f"Safety-verified alternative {top_rec} recommended by {agreement} of specialist panel "
            f"based on highest identified risk ({highest_risk})."
        )
    else:
        alt_ratio = "No alternative recommended by the specialist panel."

    return AdjudicatorOutput(
        consensus_risk_level=highest_risk,
        consensus_flagged=majority_flagged,
        consensus_summary=consensus_summary,
        agreement_level=agreement,
        recommended_alternative=top_rec,
        alternative_rationale=alt_ratio,
        cpic_note="CPIC: see individual specialist opinions for detailed citations.",
        cpic_level="informative",
        decision_confidence=avg_confidence,
        next_best_actions=[
            "Review individual specialist opinions in audit trail.",
            "Clinician to evaluate consensus recommendation.",
        ],
        human_gate_required=True,
    )


def _adjudicator(opinions: list[SpecialistOpinion]) -> AdjudicatorOutput:
    opinions_data = [
        {
            "agent": o.agent_name,
            "risk_level": o.risk_level,
            "flagged": o.flagged,
            "risk_summary": o.risk_summary,
            "recommendation": o.recommendation,
            "reasoning": o.reasoning,
            "confidence": o.confidence,
        }
        for o in opinions
    ]

    prompt = [
        {
            "role": "system",
            "content": (
                "You are the adjudicator in a pharmacogenomics panel. "
                "Review the specialist opinions below and produce a consolidated decision. "
                "Return strict JSON with keys: consensus_risk_level, consensus_flagged, consensus_summary, "
                "agreement_level (unanimous|majority|split), recommended_alternative, alternative_rationale, "
                "cpic_note, cpic_level, decision_confidence, next_best_actions, human_gate_required. "
                "Unanimous agreements should have higher confidence. "
                "Split decisions should flag for human review."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"specialist_opinions": opinions_data}, indent=2),
        },
    ]

    raw = _groq_json(prompt, max_tokens=380, temperature=0.15)
    if raw is not None:
        try:
            return AdjudicatorOutput(**raw)
        except Exception as exc:
            logger.warning("Failed to parse adjudicator JSON: %s", exc)

    return _adjudicator_fallback(opinions)


# --- Public API ---


def _convert_to_dict(op: SpecialistOpinion) -> dict[str, Any]:
    return {
        "risk_level": op.risk_level,
        "flagged": op.flagged,
        "recommendation": op.recommendation,
    }


@traceable(name="ConvenePanel", run_type="chain")
def convene_panel(
    patient: dict[str, Any],
    medication: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> tuple[list[SpecialistOpinion], AdjudicatorOutput, int]:
    start = time.perf_counter()

    phenotype = "Unknown"
    if patient.get("cyp_profiles"):
        phenotype = patient["cyp_profiles"][0].get("phenotype", "Unknown")

    monitor = get_drift_monitor()

    pharm = _pharmacologist_agent(medication, phenotype, evidence_text, evidence_sources)
    monitor.compare(
        "Pharmacologist",
        _convert_to_dict(pharm),
        _convert_to_dict(_pharmacologist_fallback(medication, phenotype, evidence_text)),
        context=f"{medication}/{phenotype}",
    )

    genetic = _geneticist_agent(phenotype, evidence_text, evidence_sources)
    monitor.compare(
        "Geneticist",
        _convert_to_dict(genetic),
        _convert_to_dict(_geneticist_fallback(phenotype, evidence_text)),
        context=phenotype,
    )

    clinic = _clinician_agent(patient, medication, evidence_text, evidence_sources)
    monitor.compare(
        "Clinician",
        _convert_to_dict(clinic),
        _convert_to_dict(_clinician_fallback(patient, medication, evidence_text)),
        context=f"{medication}/{patient.get('indication', '?')}",
    )

    opinions = [pharm, genetic, clinic]
    adjudicated = _adjudicator(opinions)

    elapsed = int((time.perf_counter() - start) * 1000)
    logger.info(
        "Panel convened — agreement=%s risk=%s (%dms)",
        adjudicated.agreement_level,
        adjudicated.consensus_risk_level,
        elapsed,
    )

    return opinions, adjudicated, elapsed
