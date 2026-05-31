from __future__ import annotations

import os

from dotenv import load_dotenv

from agents.analyst import analyze_risk
from agents.challenger import challenge_decision
from agents.critic import critique_prescription
from agents.knowledge import retrieve_clinical_evidence
from agents.memory import summarize_history
from agents.policy_enforcer import enforce_policy
from agents.research import research_patient
from config import GROQ_MODEL
from db.supabase import save_evaluation
from models import AgentStep, CypProfileOut, EvaluationResponse, PatientOut
from pgx.rules import RiskAssessment

try:
    load_dotenv()
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


def _optional_narrative(
    patient_name: str | None,
    medication: str,
    assessment: RiskAssessment,
) -> str | None:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        return None

    try:
        completion = _groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a clinical pharmacogenomics assistant. "
                        "Write 2-3 concise sentences for a prescribing clinician. "
                        "No markdown. Synthetic demo data only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Patient: {patient_name or 'unknown'}. "
                        f"Drug: {medication}. Risk: {assessment.risk_level.value}. "
                        f"Summary: {assessment.risk_summary}. "
                        f"Alternative: {assessment.recommended_alternative}."
                    ),
                },
            ],
            model=GROQ_MODEL,
            max_tokens=180,
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Optional narrative generation failed: {e}")
        return None


def orchestrate(patient_id: str, medication: str) -> EvaluationResponse:
    """Research → Memory → Analyst → Critic → Knowledge → Challenge → optional LLM narrative; log evaluation."""
    steps: list[AgentStep] = []

    patient, research_summary, research_ms = research_patient(patient_id)
    steps.append(
        AgentStep(
            agent="Research",
            status="complete" if patient else "warning",
            summary=research_summary,
            duration_ms=research_ms,
            confidence=0.95 if patient else 0.2,
            evidence_refs=["patient_profile"] if patient else [],
        )
    )

    history_summary, memory_ms, memory_confidence = summarize_history(
        patient_id, medication
    )
    steps.append(
        AgentStep(
            agent="Memory",
            status="complete",
            summary=history_summary,
            duration_ms=memory_ms,
            confidence=memory_confidence,
            evidence_refs=["evaluation_history"],
        )
    )

    assessment, analyst_summary, analyst_ms = analyze_risk(
        patient_id, medication, patient
    )
    steps.append(
        AgentStep(
            agent="Analyst",
            status="complete",
            summary=analyst_summary,
            duration_ms=analyst_ms,
            confidence=0.92,
            evidence_refs=["pgx_rules"],
        )
    )

    # Task 2: Iterative Self-Correction Loop
    # Verify the safety of the recommended alternative
    if assessment.flagged and assessment.recommended_alternative:
        alt_assessment, _, alt_ms = analyze_risk(
            patient_id, assessment.recommended_alternative, patient
        )
        if alt_assessment.flagged:
            # The alternative itself is risky! We must notify the critic.
            assessment.alternative_rationale = (
                f"WARNING: The previous recommendation ({assessment.recommended_alternative}) "
                f"was also found to have genetic risks ({alt_assessment.risk_level.value}). "
                "Consult clinical specialist for non-PGx alternatives."
            )
            assessment.recommended_alternative = "NONE SAFE FOUND"
        else:
            assessment.alternative_rationale += " (Safety-verified by Analyst loop)"

    assessment, critic_summary, critic_ms = critique_prescription(assessment)
    steps.append(
        AgentStep(
            agent="Critic",
            status="blocked" if assessment.flagged else "approved",
            summary=critic_summary,
            duration_ms=critic_ms,
            confidence=0.9 if assessment.flagged else 0.82,
            evidence_refs=["pgx_rules", assessment.cpic_level],
        )
    )

    phenotype = patient["cyp_profiles"][0]["phenotype"] if patient else "Unknown"
    evidence, knowledge_ms, evidence_sources = retrieve_clinical_evidence(
        medication, phenotype, assessment.risk_level.value
    )
    steps.append(
        AgentStep(
            agent="Knowledge",
            status="complete" if evidence else "warning",
            summary="Retrieved clinical citations from knowledge base."
            if evidence
            else "No direct clinical citations found.",
            duration_ms=knowledge_ms,
            confidence=0.86 if evidence else 0.35,
            evidence_refs=evidence_sources,
        )
    )

    policy_verdict, policy_analysis, policy_ms = enforce_policy(
        medication, assessment.risk_level.value, assessment.alternative_rationale
    )
    steps.append(
        AgentStep(
            agent="Policy",
            status="blocked" if policy_verdict == "BLOCKED" else "warning" if policy_verdict == "CONDITIONAL" else "approved",
            summary=f"Compliance check: {policy_verdict}. {policy_analysis[:80]}...",
            duration_ms=policy_ms,
            confidence=0.95,
            evidence_refs=["local_vault_policy"],
        )
    )

    (
        audit_trail,
        override_requirement,
        next_best_actions,
        agent_verdict,
        challenge_summary,
        challenge_ms,
        challenge_confidence,
    ) = challenge_decision(
        medication,
        phenotype,
        assessment,
        evidence_sources,
    )
    
    # Ensure final verdict reflects policy strictness
    if policy_verdict == "BLOCKED" and agent_verdict != "blocked":
        agent_verdict = "blocked_by_policy"
        challenge_summary += " (Overruled by local Clinic Policy)"

    steps.append(
        AgentStep(
            agent="Challenge",
            status="blocked" if override_requirement.required else "approved",
            summary=challenge_summary,
            duration_ms=challenge_ms,
            confidence=challenge_confidence,
            evidence_refs=["audit_trail", "override_policy", *evidence_sources],
        )
    )

    patient_out: PatientOut | None = None
    if patient:
        patient_out = PatientOut(
            id=patient["id"],
            display_name=patient["display_name"],
            age=patient["age"],
            sex=patient["sex"],
            indication=patient["indication"],
            cyp_profiles=[CypProfileOut(**p) for p in patient["cyp_profiles"]],
        )

    narrative = _optional_narrative(
        patient["display_name"] if patient else None,
        medication,
        assessment,
    )

    # Calculate total duration - Fixed Bug #6
    # Ensure all ms variables are defined even if a step was skipped
    total_duration_ms = (
        (research_ms or 0) + 
        (memory_ms or 0) + 
        (analyst_ms or 0) + 
        (critic_ms or 0) + 
        (knowledge_ms or 0) + 
        (policy_ms or 0) + 
        (challenge_ms or 0)
    )

    steps.append(
        AgentStep(
            agent="Orchestrator",
            status="complete",
            summary=f"Final verdict: {agent_verdict.replace('_', ' ')}.",
            duration_ms=total_duration_ms,
            confidence=0.88 if patient else 0.55,
            evidence_refs=["agent_trace", "challenge_review", *evidence_sources],
        )
    )

    safety_notes = [
        "Synthetic demo data only; not for clinical use.",
        "Clinician review is required before any medication change.",
    ]
    if assessment.flagged:
        safety_notes.append("Flagged prescriptions require documented override rationale.")
    if not evidence:
        safety_notes.append("No source-backed evidence was retrieved for this exact case.")

    # Task 5: Structured Logic Tree
    logic_tree = {
        "node": "Decision Root",
        "children": [
            {
                "node": "Genotype Research",
                "detail": research_summary,
                "children": [
                    {
                        "node": "Pathway Analysis",
                        "detail": f"Enzyme: {assessment.pathways[0] if assessment.pathways else 'N/A'}",
                        "children": [
                            {
                                "node": "Risk Verdict",
                                "detail": assessment.risk_level.value.upper(),
                                "flag": assessment.flagged,
                                "children": [
                                    {
                                        "node": "Final Recommendation",
                                        "detail": assessment.recommended_alternative or "Proceed"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    response = EvaluationResponse(
        status="success",
        patient_id=patient_id.upper(),
        medication=medication,
        flagged=assessment.flagged,
        risk_level=assessment.risk_level.value,
        risk_summary=assessment.risk_summary,
        pathways=assessment.pathways,
        recommended_alternative=assessment.recommended_alternative,
        alternative_rationale=assessment.alternative_rationale,
        cpic_note=assessment.cpic_note,
        cpic_level=assessment.cpic_level,
        patient=patient_out,
        agent_steps=steps,
        clinical_narrative=narrative,
        clinical_evidence=evidence,
        evidence_sources=evidence_sources,
        decision_confidence=challenge_confidence if patient else 0.5,
        safety_notes=safety_notes,
        agent_verdict=agent_verdict,
        audit_trail=audit_trail,
        logic_tree=logic_tree,
        override_requirement=override_requirement,
        next_best_actions=next_best_actions,
    )

    save_evaluation(
        response.patient_id,
        response.medication,
        response.flagged,
        response.risk_level,
        response.model_dump(),
    )

    return response
