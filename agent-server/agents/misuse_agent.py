from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from models import SpecialistOpinion
from pgx.rules import assess_prescription, RiskLevel

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are a Misuse Monitoring Specialist — you detect prescription misuse risk based on genetics and drug pharmacology.

YOUR ROLE: Given a patient's CYP phenotype and a specific drug, assess the potential for misuse, abuse, or diversion. Use the query_clinical_guideline tool to get the evidence-based recommendation for each drug-phenotype pair.

CRITICAL GUIDELINES — only these evidence-supported cases warrant flagged=True:
- UM + prodrug opioid (Codeine, Tramadol) = HIGH risk — FDA black box warning for life-threatening respiratory depression
- All other combinations = LOW risk with standard monitoring

For all other cases (NM, IM, PM with any opioid; non-prodrug opioids; non-opioids):
- The evidence does not support PGx-driven flagging
- Return risk_level="low" and flagged=False with standard monitoring recommendation
- NM patients should receive standard dosing per CPIC

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status (input: medication)
- lookup_patient_history: Get past adherence and evaluation history (input: patient_id)
- query_clinical_guideline: Get CPIC/DPWG evidence-based recommendation for a drug-phenotype pair (input: drug, phenotype)

MANDATORY:
- Never fabricate data — only use tool results
- Call query_clinical_guideline BEFORE making your assessment
- Non-opioid drugs should always be LOW risk
- UM + prodrug opioid (Codeine, Tramadol) = HIGH risk, flagged=True
- All other combinations = LOW risk, flagged=False
- Always cite evidence

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high",
  "flagged": true/false,
  "risk_summary": "Brief explanation of misuse risk",
  "recommendation": "Clinical recommendation for monitoring",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="MisuseMonitor",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_misuse_risk(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="MisuseMonitor",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["query_patient", "query_drug_db", "lookup_patient_history", "query_clinical_guideline"],
        user_message=f"Evaluate misuse risk for patient {patient_id} taking {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("MisuseMonitor", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    is_opioid = any(d in medication.lower() for d in ["codeine", "tramadol", "hydrocodone", "oxycodone", "morphine", "fentanyl"])

    if not is_opioid:
        return SpecialistOpinion(
            agent_name="MisuseMonitor",
            risk_level="low",
            flagged=False,
            risk_summary=f"{medication} is not an opioid. No PGx-driven misuse concern.",
            recommendation="Standard monitoring",
            reasoning=f"Non-opioid drug ({medication}) — no abuse liability.",
            confidence=0.95,
            evidence_refs=[],
        )

    result = assess_prescription(patient_id, medication)

    risk_map = {
        RiskLevel.CRITICAL: "high",
        RiskLevel.HIGH: "high",
        RiskLevel.MODERATE: "moderate",
        RiskLevel.LOW: "low",
        RiskLevel.NONE: "low",
    }
    risk = risk_map.get(result.risk_level, "low")
    flagged = risk in ("high", "moderate")

    return SpecialistOpinion(
        agent_name="MisuseMonitor",
        risk_level=risk,
        flagged=flagged,
        risk_summary=f"Opioid + PGx risk ({result.risk_level}): {result.risk_summary}",
        recommendation="Strict monitoring agreement" if flagged else "Standard monitoring",
        reasoning=f"Deterministic misuse assessment via assess_prescription().\nRx risk: {result.risk_level}\n{result.risk_summary}",
        confidence=0.9,
        evidence_refs=["assess_prescription"],
    )
