from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from models import SpecialistOpinion
from pgx.rules import assess_prescription

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
    result = assess_prescription(patient_id, medication)

    return SpecialistOpinion(
        agent_name="RxRisk",
        risk_level=result.risk_level,
        flagged=result.flagged,
        risk_summary=result.risk_summary,
        recommendation="Avoid" if result.flagged else "Standard dosing",
        reasoning=(
            f"Deterministic assessment via assess_prescription().\n"
            f"Risk: {result.risk_level}\n"
            f"Summary: {result.risk_summary}\n"
            f"Alternative: {result.recommended_alternative}"
        ),
        confidence=0.9,
        evidence_refs=["assess_prescription"],
    )
