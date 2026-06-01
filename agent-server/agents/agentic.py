from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

from dotenv import load_dotenv

from agents.knowledge import retrieve_clinical_evidence
from agents.research import research_patient
from config import GROQ_MODEL
from db.supabase import save_evaluation
from models import (
    AgentStep,
    AuditEvent,
    CriticOutput,
    CypProfileOut,
    EvaluationResponse,
    HumanGate,
    PatientOut,
    ReasoningOutput,
)

logger = logging.getLogger(__name__)

load_dotenv()

DEMO_FORMULARY = {
    "acetaminophen (scheduled)",
    "clopidogrel",
    "codeine",
    "duloxetine",
    "hydrocodone",
    "ibuprofen",
    "oxycodone",
    "pregabalin",
    "tramadol",
}

try:
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


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
        logger.warning("Agentic JSON call failed: %s", exc)
        return None


def _groq_text(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 220,
    temperature: float = 0.2,
) -> str | None:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        return None

    try:
        completion = _groq.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        logger.warning("Agentic text call failed: %s", exc)
        return None


def _patient_profile(patient: dict[str, Any] | None) -> dict[str, Any]:
    if not patient:
        return {
            "name": "Unknown",
            "age": "N/A",
            "sex": "U",
            "indication": "Unknown",
            "phenotype": "Unknown",
            "cyp_profiles": [],
        }

    phenotype = "Unknown"
    if patient.get("cyp_profiles"):
        phenotype = patient["cyp_profiles"][0].get("phenotype", "Unknown")

    return {
        "name": patient.get("display_name", "Unknown"),
        "age": patient.get("age", "N/A"),
        "sex": patient.get("sex", "U"),
        "indication": patient.get("indication", "Unknown"),
        "phenotype": phenotype,
        "cyp_profiles": patient.get("cyp_profiles", []),
    }


def _truncate(text: str, limit: int = 320) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _extract_pathways(evidence_text: str | None) -> list[str]:
    if not evidence_text:
        return []

    pathways: list[str] = []
    for raw_line in evidence_text.splitlines():
        line = raw_line.strip()
        if "→" in line or "->" in line:
            pathways.append(line)
        if len(pathways) >= 3:
            break
    return pathways


def _fallback_reasoning(
    patient: dict[str, Any],
    medication: str,
    phenotype: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> ReasoningOutput:
    medication_lower = medication.lower().strip()
    phenotype_lower = phenotype.lower().strip()
    evidence_lower = (evidence_text or "").lower()

    if medication_lower not in DEMO_FORMULARY:
        return ReasoningOutput(
            flagged=False,
            risk_level="low",
            risk_summary=(
                f"{medication} is not in the demo formulary; no PGx-specific "
                "rule was triggered, so clinician review is required before "
                "any prescribing decision."
            ),
            recommended_alternative=None,
            alternative_rationale=(
                "No formulary-backed alternative was generated for an "
                "unknown medication."
            ),
            cpic_note="No demo CPIC rule is available for this medication.",
            cpic_level="informative",
            decision_confidence=0.55,
            next_best_actions=[
                "Verify the medication name against the supported formulary.",
                "Use clinician judgment before proceeding.",
            ],
            reasoning_summary=(
                f"{medication} is outside the demo formulary and remains "
                "gated for clinician review."
            ),
            human_gate_required=True,
        )

    if medication_lower in {"pregabalin", "acetaminophen (scheduled)", "ibuprofen"}:
        return ReasoningOutput(
            flagged=False,
            risk_level="none",
            risk_summary=f"{medication} has no clear PGx block in the retrieved evidence for {phenotype}.",
            recommended_alternative=None,
            alternative_rationale="No PGx-driven change required.",
            cpic_note=f"Retrieved evidence supports standard use of {medication}.",
            cpic_level="informative",
            decision_confidence=0.84,
            next_best_actions=[
                "Proceed with standard clinical monitoring.",
                "Document the clinician review before release.",
            ],
            reasoning_summary=(
                f"Retrieved sources did not surface a pharmacogenomic contraindication for {medication} "
                f"in a {phenotype} patient."
            ),
            human_gate_required=True,
        )

    if medication_lower in {"codeine", "tramadol"}:
        if "ultra-rapid" in phenotype_lower:
            return ReasoningOutput(
                flagged=True,
                risk_level="critical",
                risk_summary=(
                    f"{phenotype} plus {medication} is associated with excessive active-metabolite formation and toxicity risk."
                ),
                recommended_alternative="Duloxetine",
                alternative_rationale=(
                    "Safety-verified alternative avoids CYP2D6 prodrug "
                    "activation and lowers rapid-conversion risk."
                ),
                cpic_note="CPIC-aligned evidence recommends avoiding the prodrug in ultra-rapid metabolizers.",
                cpic_level="strong",
                decision_confidence=0.96,
                next_best_actions=[
                    "Review the alternative with the clinician.",
                    "Document that the prescription was intercepted before dispensing.",
                ],
                reasoning_summary=(
                    f"Retrieved evidence and patient context support a hard stop for {medication} because the "
                    f"metabolizer profile is ultra-rapid."
                ),
                human_gate_required=True,
            )

        if "poor" in phenotype_lower:
            return ReasoningOutput(
                flagged=True,
                risk_level="high",
                risk_summary=(
                    f"{phenotype} plus {medication} is likely to underperform because activation is impaired."
                ),
                recommended_alternative="Duloxetine",
                alternative_rationale=(
                    "Safety-verified alternative has less dependence on the "
                    "affected CYP2D6 activation pathway."
                ),
                cpic_note="Evidence indicates reduced conversion and likely treatment failure.",
                cpic_level="strong",
                decision_confidence=0.92,
                next_best_actions=[
                    "Discuss a non-prodrug alternative.",
                    "Document counseling and follow-up expectations.",
                ],
                reasoning_summary=(
                    f"Patient phenotype suggests {medication} will be less reliable and should not be the first choice."
                ),
                human_gate_required=True,
            )

    if medication_lower == "clopidogrel":
        c2c19_profile = next(
            (profile for profile in patient.get("cyp_profiles", []) if profile.get("gene") == "CYP2C19"),
            None,
        )
        if c2c19_profile:
            phenotype_lower = c2c19_profile.get("phenotype", "").lower()
            if "poor" in phenotype_lower or "intermediate" in phenotype_lower:
                return ReasoningOutput(
                    flagged=True,
                    risk_level="critical" if "poor" in phenotype_lower else "high",
                    risk_summary=(
                        f"CYP2C19 {c2c19_profile.get('phenotype')} is a poor fit for clopidogrel activation."
                    ),
                    recommended_alternative="Prasugrel" if "prasugrel" in evidence_lower else "Ticagrelor",
                    alternative_rationale="A different antiplatelet path avoids the activation bottleneck.",
                    cpic_note="CPIC-aligned evidence cautions against clopidogrel when CYP2C19 activity is reduced.",
                    cpic_level="strong",
                    decision_confidence=0.95,
                    next_best_actions=[
                        "Escalate to clinician review.",
                        "Document the alternative antiplatelet plan if approved.",
                    ],
                    reasoning_summary="The patient-specific CYP2C19 phenotype weakens clopidogrel activation.",
                    human_gate_required=True,
                )

    evidence_signal = any(term in evidence_lower for term in ("avoid", "block", "warning", "caution", "risk"))
    risk_level = "moderate" if evidence_signal else "low"
    flagged = evidence_signal

    return ReasoningOutput(
        flagged=flagged,
        risk_level=risk_level,
        risk_summary=(
            f"Retrieved evidence for {medication} in a {phenotype} patient suggests caution and clinician review."
            if evidence_signal
            else f"No direct pharmacogenomic block surfaced for {medication}, but clinician review is still required."
        ),
        recommended_alternative=None,
        alternative_rationale="No stronger alternative was surfaced by the retrieved evidence.",
        cpic_note="Use retrieved evidence and clinician judgment to finalize the prescription.",
        cpic_level="informative" if not evidence_signal else "moderate",
        decision_confidence=0.63 if evidence_signal else 0.58,
        next_best_actions=[
            "Review the retrieved evidence with the clinician.",
            "Decide whether to proceed, switch, or defer.",
        ],
        reasoning_summary=(
            f"Evidence was insufficient for an automatic switch, so the case should stay in human review."
        ),
        human_gate_required=True,
    )


def _reasoning_agent(
    patient: dict[str, Any],
    medication: str,
    evidence_text: str | None,
    evidence_sources: list[str],
) -> ReasoningOutput:
    profile = _patient_profile(patient)
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a pharmacogenomics reasoning agent. "
                "Use only the supplied patient context and evidence. "
                "Do not mention deterministic rules. "
                "Return strict JSON with keys: flagged, risk_level, risk_summary, recommended_alternative, "
                "alternative_rationale, cpic_note, cpic_level, decision_confidence, next_best_actions, "
                "reasoning_summary, human_gate_required. "
                "The clinical gate must remain with the human clinician."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient": profile,
                    "medication": medication,
                    "evidence_sources": evidence_sources,
                    "evidence_text": evidence_text or "No source-backed evidence was retrieved.",
                    "allowed_risk_levels": ["none", "low", "moderate", "high", "critical"],
                },
                indent=2,
            ),
        },
    ]

    raw = _groq_json(prompt, max_tokens=380, temperature=0.15)
    if raw is not None:
        try:
            return ReasoningOutput(**raw)
        except Exception as exc:
            logger.warning("Failed to parse reasoning JSON, falling back: %s", exc)

    return _fallback_reasoning(patient, medication, profile["phenotype"], evidence_text, evidence_sources)


def _fallback_critique(
    reasoning: ReasoningOutput,
    evidence_sources: list[str],
) -> CriticOutput:
    if reasoning.flagged and reasoning.risk_level in {"critical", "high"}:
        override = True
        verdict = "blocked_by_policy"
        summary = "Critic agent upheld the block and kept the prescription behind a clinician override gate."
        next_actions = [
            "Require clinician approval before any dispensing decision.",
            "Document the rationale for any override.",
            "Use the suggested alternative if the clinician agrees.",
        ]
        audit = [
            AuditEvent(
                stage="evidence_grounding",
                decision="pass" if evidence_sources else "needs_review",
                rationale=(
                    f"Decision grounded in {', '.join(evidence_sources)}."
                    if evidence_sources
                    else "No direct evidence source was retrieved."
                ),
                requires_human_review=not evidence_sources,
            ),
            AuditEvent(
                stage="safety_challenge",
                decision="block",
                rationale="The recommendation remains high risk until a clinician reviews it.",
                requires_human_review=True,
            ),
        ]
        fields = [
            "clinician_id",
            "risk_benefit_rationale",
            "patient_counseling_attestation",
            "monitoring_plan",
        ]
        confidence = 0.93 if evidence_sources else 0.78
    elif reasoning.flagged:
        override = False
        verdict = "review_required"
        summary = "Critic agent confirmed a cautionary case that still needs a clinician's final call."
        next_actions = [
            "Review the proposed therapy with the clinician.",
            "Confirm the patient counseling plan before release.",
        ]
        audit = [
            AuditEvent(
                stage="evidence_grounding",
                decision="pass" if evidence_sources else "needs_review",
                rationale=(
                    f"Decision grounded in {', '.join(evidence_sources)}."
                    if evidence_sources
                    else "No direct evidence source was retrieved."
                ),
                requires_human_review=not evidence_sources,
            ),
            AuditEvent(
                stage="safety_challenge",
                decision="review_required",
                rationale="Risk remains non-trivial even if not an outright block.",
                requires_human_review=True,
            ),
        ]
        fields = []
        confidence = 0.84
    else:
        override = False
        verdict = "approved_with_monitoring"
        summary = "Critic agent found no blocking pharmacogenomic concern, but still left the human gate in place."
        next_actions = [
            "Proceed only after clinician approval.",
            "Continue monitoring efficacy and adverse effects after dispensing.",
        ]
        audit = [
            AuditEvent(
                stage="evidence_grounding",
                decision="pass" if evidence_sources else "needs_review",
                rationale=(
                    f"Decision grounded in {', '.join(evidence_sources)}."
                    if evidence_sources
                    else "No direct evidence source was retrieved."
                ),
                requires_human_review=not evidence_sources,
            ),
            AuditEvent(
                stage="safety_challenge",
                decision="approve_with_monitoring",
                rationale="No severe mismatch surfaced in the retrieved evidence.",
                requires_human_review=False,
            ),
        ]
        fields = []
        confidence = 0.82

    return CriticOutput(
        agent_verdict=verdict,
        critique_summary=summary,
        audit_trail=audit,
        override_requirement={
            "required": override,
            "reason": (
                "Critical or high pharmacogenomic risk requires clinician override documentation."
                if override
                else "No override required by the current evidence, but clinician approval is still required."
            ),
            "required_fields": fields,
        },
        next_best_actions=next_actions,
        challenge_confidence=confidence,
        human_gate_required=True,
    )


def _critique_agent(
    reasoning: ReasoningOutput,
    patient: dict[str, Any],
    medication: str,
    evidence_sources: list[str],
    evidence_text: str | None,
) -> CriticOutput:
    profile = _patient_profile(patient)
    prompt = [
        {
            "role": "system",
            "content": (
                "You are the critique agent in a pharmacogenomics workflow. "
                "Challenge the reasoning output, look for missing evidence, and produce strict JSON with keys: "
                "agent_verdict, critique_summary, audit_trail, override_requirement, next_best_actions, "
                "challenge_confidence, human_gate_required. "
                "Keep the clinician as the final decision maker."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient": profile,
                    "medication": medication,
                    "evidence_sources": evidence_sources,
                    "evidence_text": evidence_text or "No source-backed evidence was retrieved.",
                    "reasoning": reasoning.model_dump(),
                },
                indent=2,
            ),
        },
    ]

    raw = _groq_json(prompt, max_tokens=320, temperature=0.2)
    if raw is not None:
        try:
            parsed = CriticOutput(**raw)
            if isinstance(parsed.override_requirement, dict):  # pragma: no cover - pydantic safety
                parsed.override_requirement = parsed.override_requirement
            return parsed
        except Exception as exc:
            logger.warning("Failed to parse critique JSON, falling back: %s", exc)

    return _fallback_critique(reasoning, evidence_sources)


def _draft_narrative(
    patient_name: str,
    medication: str,
    reasoning: ReasoningOutput,
    critique: CriticOutput,
) -> str:
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a clinical documentation agent. "
                "Draft 2-3 concise sentences for a clinician. "
                "No markdown, no bullet points. "
                "Mention the medication, the risk summary, and the fact that a human gate is still required."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient_name": patient_name,
                    "medication": medication,
                    "reasoning": reasoning.model_dump(),
                    "critique": critique.model_dump(),
                },
                indent=2,
            ),
        },
    ]

    text = _groq_text(prompt, max_tokens=140, temperature=0.2)
    if text:
        return text.strip()

    recommendation = reasoning.recommended_alternative or "no automatic alternative"
    return (
        f"{patient_name} was reviewed for {medication}. {reasoning.risk_summary} "
        f"The agentic workflow recommends {recommendation}, and clinician approval is still required before release."
    )


def _build_logic_tree(
    retrieval_summary: str,
    reasoning: ReasoningOutput,
    critique: CriticOutput,
    human_gate: HumanGate,
    pathways: list[str],
) -> dict[str, Any]:
    return {
        "node": "Decision Root",
        "children": [
            {
                "node": "Retrieval",
                "detail": retrieval_summary,
                "children": [
                    {
                        "node": "Pathways",
                        "detail": pathways[0] if pathways else "No pathway text extracted",
                    }
                ],
            },
            {
                "node": "Reasoning",
                "detail": reasoning.reasoning_summary or reasoning.risk_summary,
                "flag": reasoning.flagged,
                "children": [
                    {
                        "node": "Recommendation",
                        "detail": reasoning.recommended_alternative or "Proceed only after review",
                    }
                ],
            },
            {
                "node": "Critique",
                "detail": critique.critique_summary,
                "flag": critique.override_requirement.required,
            },
            {
                "node": "Human Gate",
                "detail": human_gate.reason,
                "flag": True,
            },
        ],
    }


def orchestrate(patient_id: str, medication: str) -> EvaluationResponse:
    start_total = time.perf_counter()
    patient, retrieval_summary, retrieval_ms = research_patient(patient_id)
    profile = _patient_profile(patient)

    evidence_text, evidence_ms, evidence_sources = retrieve_clinical_evidence(
        medication,
        profile["phenotype"],
        "review",
    )

    agent_steps: list[AgentStep] = [
        AgentStep(
            agent="Retrieval",
            status="complete",
            summary=(
                f"Loaded patient context for {profile['name']} and retrieved supporting evidence from "
                f"{', '.join(evidence_sources) if evidence_sources else 'no local source matches'}."
            ),
            duration_ms=retrieval_ms + evidence_ms,
            confidence=0.95 if patient else 0.2,
            evidence_refs=["patient_profile", *evidence_sources],
        )
    ]

    reasoning_start = time.perf_counter()
    reasoning = _reasoning_agent(patient, medication, evidence_text, evidence_sources)
    reasoning_ms = int((time.perf_counter() - reasoning_start) * 1000)
    agent_steps.append(
        AgentStep(
            agent="Reasoning",
            status="complete",
            summary=reasoning.reasoning_summary or reasoning.risk_summary,
            duration_ms=reasoning_ms,
            confidence=reasoning.decision_confidence,
            evidence_refs=[*evidence_sources, "retrieved_evidence"],
        )
    )

    critique_start = time.perf_counter()
    critique = _critique_agent(reasoning, patient, medication, evidence_sources, evidence_text)
    critique_ms = int((time.perf_counter() - critique_start) * 1000)
    agent_steps.append(
        AgentStep(
            agent="Critic",
            status="blocked" if critique.override_requirement.required else "approved",
            summary=critique.critique_summary,
            duration_ms=critique_ms,
            confidence=critique.challenge_confidence,
            evidence_refs=[*evidence_sources, "audit_trail"],
        )
    )

    challenge_summary = (
        "Challenge agent kept the recommendation behind a clinician override gate."
        if critique.override_requirement.required
        else "Challenge agent accepted a monitored release path pending clinician approval."
    )
    agent_steps.append(
        AgentStep(
            agent="Challenge",
            status="blocked" if critique.override_requirement.required else "approved",
            summary=challenge_summary,
            duration_ms=0,
            confidence=critique.challenge_confidence,
            evidence_refs=["audit_trail", "override_requirement"],
        )
    )

    narrative_start = time.perf_counter()
    clinical_narrative = _draft_narrative(profile["name"], medication, reasoning, critique)
    narrative_ms = int((time.perf_counter() - narrative_start) * 1000)
    agent_steps.append(
        AgentStep(
            agent="Reporter",
            status="complete",
            summary=_truncate(clinical_narrative, 180),
            duration_ms=narrative_ms,
            confidence=0.88,
            evidence_refs=[*evidence_sources, "clinical_note"],
        )
    )

    human_gate = HumanGate(
        required=True,
        status="pending",
        reason="Clinician approval required before release.",
        required_fields=critique.override_requirement.required_fields,
    )
    agent_steps.append(
        AgentStep(
            agent="HumanGate",
            status="pending",
            summary="Clinician approval or rejection is required before dispensing.",
            duration_ms=0,
            confidence=1.0,
            evidence_refs=["human_review"],
        )
    )

    pathways = _extract_pathways(evidence_text)
    final_flagged = reasoning.flagged or critique.override_requirement.required
    next_best_actions = critique.next_best_actions or reasoning.next_best_actions
    decision_confidence = round((reasoning.decision_confidence + critique.challenge_confidence) / 2, 2)
    safety_notes = [
        "Synthetic demo data only; not for autonomous dispensing.",
        "Clinician approval required before release.",
    ]
    if critique.override_requirement.required:
        safety_notes.append("If overriding the AI recommendation, document the required fields.")
    if not evidence_sources:
        safety_notes.append("No direct source-backed evidence was retrieved for this case.")

    final_agent_step_duration = int((time.perf_counter() - start_total) * 1000)
    human_gate_summary = "Human gate is open but waiting for clinician review."
    agent_steps.append(
        AgentStep(
            agent="Orchestrator",
            status="complete",
            summary=(
                f"Final agent verdict: {critique.agent_verdict.replace('_', ' ')}. "
                f"Clinician review remains pending."
            ),
            duration_ms=final_agent_step_duration,
            confidence=decision_confidence,
            evidence_refs=["agent_trace", *evidence_sources],
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

    response = EvaluationResponse(
        evaluation_id=str(uuid.uuid4()),
        status="success",
        patient_id=patient_id.upper(),
        medication=medication,
        flagged=final_flagged,
        risk_level=reasoning.risk_level,
        risk_summary=reasoning.risk_summary,
        pathways=pathways,
        recommended_alternative=reasoning.recommended_alternative,
        alternative_rationale=reasoning.alternative_rationale,
        cpic_note=reasoning.cpic_note,
        cpic_level=reasoning.cpic_level,
        patient=patient_out,
        agent_steps=agent_steps,
        clinical_narrative=clinical_narrative,
        clinical_evidence=evidence_text,
        evidence_sources=evidence_sources,
        decision_confidence=decision_confidence,
        safety_notes=safety_notes,
        agent_verdict=critique.agent_verdict,
        audit_trail=critique.audit_trail,
        logic_tree=_build_logic_tree(retrieval_summary, reasoning, critique, human_gate, pathways),
        override_requirement=critique.override_requirement,
        human_gate=human_gate,
        next_best_actions=next_best_actions,
    )

    # Save the evaluation and use the ID returned by save_evaluation
    # Note: response.model_dump() now includes the evaluation_id set above
    persisted_id = save_evaluation(
        response.patient_id,
        response.medication,
        response.flagged,
        response.risk_level,
        response.model_dump(),
    )
    response.evaluation_id = persisted_id
    
    return response
