from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from models import SpecialistOpinion
from pgx.rules import assess_prescription, RiskLevel

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
    result = assess_prescription(patient_id, medication)

    if result.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        risk = "moderate"
        flagged = True
        summary = (
            f"{result.risk_summary} — High PGx risk may reduce adherence "
            f"due to side effects or lack of efficacy."
        )
    elif result.risk_level == RiskLevel.MODERATE:
        risk = "low"
        flagged = False
        summary = f"{result.risk_summary} — Monitor for adherence but PGx-driven risk is manageable."
    else:
        risk = "low"
        flagged = False
        summary = f"Standard adherence risk for {medication}. No PGx-driven concern."

    return SpecialistOpinion(
        agent_name="Adherence",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Monitor adherence" if flagged else "Standard monitoring",
        reasoning=f"Deterministic adherence derived from assess_prescription().\nRx risk: {result.risk_level}\n{result.risk_summary}",
        confidence=0.85,
        evidence_refs=["assess_prescription"],
    )
