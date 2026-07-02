from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from agents.base import run_specialist_agent
from models import SpecialistOpinion
from pgx.rules import assess_prescription

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are a Cost Navigator Specialist — you find affordable, phenotype-safe therapeutic alternatives based on patient genetics and drug properties.

YOUR ROLE: Given a patient's CYP phenotype and a prescribed drug, recommend cost-effective alternatives that are safe for their genetic profile. Consider:
- Prodrugs in UM patients cause toxicity → avoid → switch to non-prodrug alternative
- Prodrugs in PM patients cause no effect → avoid → switch to non-prodrug alternative
- Non-prodrug drugs in any phenotype → generally safe, standard cost considerations
- Alternatives should be phenotype-safe AND cost-effective (fewer adverse events = lower total cost)
- If the drug has no known alternatives, note that clearly

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including alternatives (input: medication)
- query_alternative_drugs: Get structured alternative drug options (input: drug, phenotype)

MANDATORY:
- Never fabricate data — only use tool results
- Always explain WHY an alternative is more cost-effective
- If no alternatives exist, state "no alternatives identified" — do not make up drugs
- Always cite evidence

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate",
  "flagged": true/false,
  "risk_summary": "Cost analysis summary with alternative recommendation",
  "recommendation": "Preferred alternative drug name or current drug if none found",
  "reasoning": "Step-by-step cost-effectiveness reasoning",
  "confidence": 0.0-1.0
}"""


def _clamp_cost_opinion(opinion: dict) -> dict:
    clamped = dict(opinion)
    clamped["flagged"] = False
    raw_risk = clamped.get("risk_level", "low")
    clamped["risk_level"] = raw_risk if raw_risk in ("low", "moderate") else "low"
    return clamped


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="CostNavigator",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_cost(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="CostNavigator",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["query_patient", "query_drug_db", "query_alternative_drugs"],
        user_message=f"Find cost-effective alternatives for patient {patient_id} prescribed {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        post_process=_clamp_cost_opinion,
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    result = assess_prescription(patient_id, medication)
    preferred_alt = result.recommended_alternative

    if result.flagged and preferred_alt and preferred_alt != medication:
        summary = (
            f"Switch from {medication} to {preferred_alt}. "
            f"PGx risk ({result.risk_level}) makes the switch cost-effective "
            f"by avoiding adverse events and therapeutic failure."
        )
    elif preferred_alt:
        summary = f"{preferred_alt} is a cost-effective alternative for {medication}."
    else:
        summary = f"No alternative identified for {medication}. Current drug is the most cost-effective PGx-safe option."

    return SpecialistOpinion(
        agent_name="CostNavigator",
        risk_level="low",
        flagged=False,
        risk_summary=summary,
        recommendation=preferred_alt or medication,
        reasoning=f"Deterministic cost assessment via assess_prescription().\nRisk: {result.risk_level}\nAlternative: {result.recommended_alternative}\nRationale: {result.alternative_rationale}",
        confidence=0.85,
        evidence_refs=["assess_prescription"],
    )
