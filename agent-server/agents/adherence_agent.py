from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype as _extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are an Adherence Monitoring Specialist — you predict whether a patient is likely to adhere to a prescribed medication based on their genetic profile.

YOUR ROLE: Given a patient's CYP phenotype and a specific drug, assess the realistic adherence risk. Consider:
- Whether the drug is a prodrug (requires metabolic activation)
- Whether the patient's phenotype will cause unpleasant side effects (UM + prodrug → toxicity)
- Whether the patient will feel NO benefit (PM + prodrug → no effect → abandonment)
- Whether the drug is even metabolized by the patient's relevant CYP enzyme
- If the drug is NOT CYP-metabolized, phenotype is irrelevant — standard adherence applies

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status (input: medication)
- lookup_patient_history: Get past adherence and evaluation history (input: patient_id)

MANDATORY:
- Never fabricate data — only use tool results
- If the drug is NOT metabolized by the patient's CYP enzymes, set risk to "low"
- A patient who feels NO benefit (PM + prodrug) has the HIGHEST non-adherence risk
- A patient who feels toxicity (UM + prodrug) has MODERATE non-adherence risk
- Always cite evidence
- Require human review for high/moderate risk

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high",
  "flagged": true/false,
  "risk_summary": "Brief explanation of adherence risk",
  "recommendation": "Intervention recommendation",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="Adherence",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_adherence(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="Adherence",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["query_patient", "query_drug_db", "lookup_patient_history"],
        user_message=f"Evaluate adherence risk for patient {patient_id} taking {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("Adherence", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    phenotype = _extract_phenotype(patient_data)
    is_prodrug = "Is prodrug: True" in drug_data
    pheno_key = phenotype.lower() if phenotype else ""

    drug_enzyme = ""
    try:
        parsed = json.loads(drug_data)
        inner = parsed.get("result", drug_data)
    except (json.JSONDecodeError, TypeError):
        inner = str(drug_data)
    for line in inner.split("\n"):
        if line.startswith("Enzyme:"):
            drug_enzyme = line.split(":", 1)[1].strip()
            break

    if drug_enzyme in ("", "—"):
        risk = "low"
        flagged = False
        summary = f"{medication} is not CYP-metabolized. Standard adherence applies."
    elif pheno_key == "ultra-rapid metabolizer" and is_prodrug:
        risk = "moderate"
        flagged = True
        summary = f"UM + prodrug: potential toxicity side effects may reduce adherence."
    elif pheno_key == "poor metabolizer" and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"PM + prodrug: no therapeutic effect — highest abandonment risk."
    else:
        risk = "low"
        flagged = False
        summary = f"Standard adherence risk for {medication} in {phenotype}."

    return SpecialistOpinion(
        agent_name="Adherence",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Monitor adherence" if flagged else "Standard monitoring",
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )
