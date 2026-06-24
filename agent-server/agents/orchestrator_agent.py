from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid

from dotenv import load_dotenv

from config import GROQ_MODEL
from models import (
    AgentStep,
    AuditEvent,
    EvaluationResponse,
    HumanGate,
    PatientOut,
    CypProfileOut,
    SpecialistOpinion,
)

logger = logging.getLogger(__name__)
load_dotenv()

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

ADJUDICATOR_PROMPT = """You are the PGx Adjudicator — you synthesize opinions from 5 specialist agents into a final prescribing decision.

SPECIALIST INPUTS:
1. RxRisk: Drug-gene interaction risk assessment
2. Evidence: Clinical evidence from CPIC/FDA/PharmGKB guidelines
3. Adherence: Predicted patient adherence risk based on phenotype
4. MisuseMonitor: Prescription misuse and abuse potential
5. CostNavigator: Cost-effective alternative analysis

YOUR JOB:
- Review all 5 specialist opinions
- Determine consensus risk level
- Decide if the prescription should be blocked
- Recommend an alternative if needed
- Produce a clinical narrative explaining the decision

RULES:
- If ANY specialist flags high risk → block the prescription
- If ALL specialists agree low risk → approve
- Always require human gate review
- Cite the specialist opinions that drove the decision

Return JSON:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "agent_verdict": "blocked" | "review_required" | "approved",
  "clinical_narrative": "Concise clinical explanation",
  "recommended_alternative": "Drug name or null",
  "alternative_rationale": "Why this alternative is safer",
  "decision_confidence": 0.0-1.0,
  "safety_notes": ["note1", "note2"]
}"""


async def evaluate_prescription(patient_id: str, medication: str) -> EvaluationResponse:
    start_time = time.perf_counter()
    evaluation_id = str(uuid.uuid4())

    patient_data = _get_patient_data(patient_id)
    patient_out = _build_patient_out(patient_data) if patient_data else None

    opinions = await _run_specialists(patient_id, medication)
    agent_steps = _build_agent_steps(opinions, start_time)

    adjudicated = await _adjudicate(opinions, patient_id, medication)

    risk_level = adjudicated.get("risk_level", "low")
    is_flagged = risk_level in ("high", "critical", "moderate")

    safety_notes = [
        "Synthetic demo data only; not for autonomous dispensing.",
        "Clinician approval required before release.",
    ]
    if any(o.confidence < 0.6 for o in opinions):
        safety_notes.append("Low confidence in one or more specialist assessments.")

    response = EvaluationResponse(
        evaluation_id=evaluation_id,
        status="success",
        patient_id=patient_id.upper(),
        medication=medication,
        flagged=is_flagged,
        risk_level=risk_level,
        risk_summary=adjudicated.get("clinical_narrative", "Evaluation complete."),
        pathways=[],
        recommended_alternative=adjudicated.get("recommended_alternative"),
        alternative_rationale=adjudicated.get("alternative_rationale", ""),
        cpic_note="CPIC: see individual specialist evidence.",
        cpic_level="informative",
        patient=patient_out,
        agent_steps=agent_steps,
        clinical_narrative=adjudicated.get("clinical_narrative"),
        clinical_evidence=_build_evidence_summary(opinions),
        evidence_sources=[ref for o in opinions for ref in o.evidence_refs],
        decision_confidence=adjudicated.get("decision_confidence", 0.8),
        safety_notes=safety_notes,
        agent_verdict=adjudicated.get("agent_verdict", "review_required"),
        audit_trail=_build_audit_trail(opinions),
        logic_tree=_build_logic_tree(opinions),
        human_gate=HumanGate(
            required=True,
            status="pending",
            reason="Clinician approval required before release.",
        ),
        next_best_actions=[
            "Review specialist opinions in agent pipeline.",
            "Check patient profile and evidence sources.",
            "Approve or reject via human gate endpoint.",
        ],
    )

    try:
        from db.database import save_evaluation
        persisted = save_evaluation(
            response.patient_id,
            response.medication,
            response.flagged,
            response.risk_level,
            response.model_dump(),
        )
        response.evaluation_id = persisted
    except Exception as exc:
        logger.warning("Could not persist evaluation: %s", exc)

    return response


def _get_patient_data(patient_id: str) -> dict | None:
    try:
        from db.database import get_patient_by_id
        return get_patient_by_id(patient_id)
    except Exception as exc:
        logger.warning("Could not fetch patient %s: %s", patient_id, exc)
        return None


def _build_patient_out(data: dict) -> PatientOut:
    return PatientOut(
        id=data["id"],
        display_name=data["display_name"],
        age=data["age"],
        sex=data["sex"],
        indication=data["indication"],
        cyp_profiles=[CypProfileOut(**p) for p in data.get("cyp_profiles", [])],
    )


async def _run_specialists(patient_id: str, medication: str) -> list[SpecialistOpinion]:
    from agents.rx_risk_agent import evaluate_rx_risk
    from agents.evidence_agent import retrieve_evidence
    from agents.adherence_agent import evaluate_adherence
    from agents.misuse_agent import evaluate_misuse_risk
    from agents.cost_navigator_agent import evaluate_cost

    phenotype = await _get_phenotype_from_patient(patient_id)

    results = await asyncio.gather(
        evaluate_rx_risk(patient_id, medication),
        retrieve_evidence(medication, phenotype),
        evaluate_adherence(patient_id, medication),
        evaluate_misuse_risk(patient_id, medication),
        evaluate_cost(patient_id, medication),
    )
    return list(results)


async def _get_phenotype_from_patient(patient_id: str) -> str:
    try:
        from agents.mcp_client import call_tool as _mcp_call
        from pgx.patients import extract_phenotype
        data = await _mcp_call("query_patient", {"patient_id": patient_id})
        return extract_phenotype(data)
    except Exception:
        return "unknown"


async def _adjudicate(opinions: list[SpecialistOpinion], patient_id: str, medication: str) -> dict:
    if _groq and os.environ.get("GROQ_API_KEY"):
        try:
            return await _llm_adjudicate(opinions)
        except Exception as exc:
            logger.warning("LLM adjudication failed, using deterministic: %s", exc)

    return _deterministic_adjudicate(opinions, medication)


async def _llm_adjudicate(opinions: list[SpecialistOpinion]) -> dict:
    opinions_json = json.dumps([o.model_dump() for o in opinions], indent=2)

    messages = [
        {"role": "system", "content": ADJUDICATOR_PROMPT},
        {"role": "user", "content": f"Synthesize these specialist opinions for final decision:\n\n{opinions_json}"},
    ]

    response = await asyncio.to_thread(
        _groq.chat.completions.create,
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.3,
    )

    content = response.choices[0].message.content or ""
    parsed = _parse_adjudication(content)
    if not parsed or "risk_level" not in parsed:
        raise ValueError(f"LLM returned unparseable adjudication: {content[:200]}")
    return parsed


def _deterministic_adjudicate(opinions: list[SpecialistOpinion], medication: str) -> dict:
    risk_levels = {"critical": 4, "high": 3, "moderate": 2, "low": 1}
    max_risk = "low"
    max_score = 0
    any_flagged = False

    for o in opinions:
        score = risk_levels.get(o.risk_level, 1)
        if score > max_score:
            max_score = score
            max_risk = o.risk_level
        if o.flagged:
            any_flagged = True

    is_blocked = any_flagged or max_score >= 3
    alternative = None
    alt_rationale = ""
    for o in opinions:
        if o.agent_name == "CostNavigator" and o.recommendation and o.recommendation != medication:
            alternative = o.recommendation
            alt_rationale = o.risk_summary
            break
    if not alternative:
        for o in opinions:
            if o.recommendation and "avoid" in o.recommendation.lower():
                alt_match = __import__("re").search(r"(Duloxetine|Pregabalin|Acetaminophen)", o.reasoning + " " + o.risk_summary)
                if alt_match:
                    alternative = alt_match.group(1)
                    alt_rationale = f"Recommended by {o.agent_name}: {o.risk_summary}"
                    break

    agent_labels = [o.agent_name for o in opinions]
    agent_risks = ", ".join(f"{a}={o.risk_level}" for a, o in zip(agent_labels, opinions))

    return {
        "risk_level": max_risk,
        "agent_verdict": "blocked" if is_blocked else "review_required",
        "clinical_narrative": f"5-agent evaluation: {agent_risks}. {'BLOCKED' if is_blocked else 'Review required'}.",
        "recommended_alternative": alternative,
        "alternative_rationale": alt_rationale or "No alternative identified.",
        "decision_confidence": round(sum(o.confidence for o in opinions) / len(opinions), 2) if opinions else 0.8,
        "safety_notes": [],
    }


def _parse_adjudication(text: str) -> dict:
    import re
    if not text:
        return {}
    json_match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _build_agent_steps(opinions: list[SpecialistOpinion], start_time: float) -> list[AgentStep]:
    steps = []
    for o in opinions:
        steps.append(AgentStep(
            agent=o.agent_name,
            status="complete",
            summary=o.risk_summary[:200] if o.risk_summary else f"{o.agent_name} evaluation complete",
            duration_ms=0,
            confidence=o.confidence,
            evidence_refs=o.evidence_refs,
        ))
    steps.append(AgentStep(
        agent="HumanGate",
        status="pending",
        summary="Clinician approval required before release.",
        duration_ms=0,
        confidence=1.0,
        evidence_refs=["human_review"],
    ))
    return steps


def _build_evidence_summary(opinions: list[SpecialistOpinion]) -> str:
    parts = []
    for o in opinions:
        refs = ", ".join(o.evidence_refs) if o.evidence_refs else "no sources"
        parts.append(f"[{o.agent_name}] Sources: {refs} | {o.risk_summary}")
    return "\n".join(parts)


def _build_audit_trail(opinions: list[SpecialistOpinion]) -> list[AuditEvent]:
    return [
        AuditEvent(
            stage=o.agent_name,
            decision="blocked" if o.flagged else "cleared",
            rationale=o.risk_summary,
            requires_human_review=o.flagged,
        )
        for o in opinions
    ]


def _build_logic_tree(opinions: list[SpecialistOpinion]) -> dict:
    children = []
    for o in opinions:
        children.append({
            "node": o.agent_name,
            "detail": o.risk_summary[:150],
            "flag": o.flagged,
        })
    children.append({
        "node": "Human Gate",
        "detail": "Clinician approval required before release.",
        "flag": True,
    })
    return {"node": "Multi-Agent Orchestrator", "children": children}

