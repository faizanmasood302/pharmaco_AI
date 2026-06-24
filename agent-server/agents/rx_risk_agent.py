from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are an Rx Risk Specialist — a pharmacogenomic drug-gene interaction expert.

YOUR ROLE: Evaluate whether a prescribed drug is safe for a specific patient based on their genetic profile.

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status, alternatives (input: medication)

PROCESS:
1. Call query_patient to get the patient's CYP phenotype
2. Call query_drug_db to get the drug's properties
3. Determine risk:
   - Ultra-Rapid Metabolizer (UM) + prodrug → HIGH risk (toxicity — drug converts too fast)
   - Poor Metabolizer (PM) + prodrug → HIGH risk (no therapeutic effect)
   - Normal Metabolizer (NM) → LOW risk
   - Any + non-prodrug → MODERATE risk (monitor)
4. Recommend alternative if risk is high

MANDATORY:
- Never fabricate data — only use tool results
- Always cite evidence
- Require human review for high/critical risk

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "flagged": true/false,
  "risk_summary": "Brief explanation",
  "recommendation": "Avoid" | "Use with caution" | "Standard dosing",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="RxRisk",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_rx_risk(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="RxRisk",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["query_patient", "query_drug_db"],
        user_message=f"Evaluate {medication} for patient {patient_id}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("RxRisk", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    is_prodrug = "prodrug" in drug_data.lower()
    pheno = extract_phenotype(patient_data)
    is_um = pheno == "ultra-rapid metabolizer"
    is_pm = pheno == "poor metabolizer"

    if is_um and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"Ultra-rapid metabolizer + prodrug ({medication}) → risk of toxicity"
    elif is_pm and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"Poor metabolizer + prodrug ({medication}) → no therapeutic effect"
    else:
        risk = "low"
        flagged = False
        summary = f"Standard risk profile for {medication}"

    return SpecialistOpinion(
        agent_name="RxRisk",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Avoid" if flagged else "Standard dosing",
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )
