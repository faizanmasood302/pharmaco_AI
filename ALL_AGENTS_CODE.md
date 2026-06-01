# All Agents Code

This file contains the consolidated code for all agents in the `agent-server/agents/` directory.

## `adherence.py`

```python
from __future__ import annotations

import os
import json
import logging
from dotenv import load_dotenv

from db.supabase import create_adherence_plan, get_adherence_plan, submit_check_in
from config import GROQ_MODEL

logger = logging.getLogger(__name__)

try:
    load_dotenv()
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


def start_adherence_monitoring(patient_id: str, medication: str) -> dict:
    plan = create_adherence_plan(patient_id, medication)
    if not plan:
        return {"status": "error", "message": "Could not create adherence plan"}
    return {
        "status": "success",
        "plan_id": plan["id"],
        "patient_id": patient_id.upper(),
        "medication": medication,
        "check_ins": plan.get("check_ins") or _fetch_check_ins(plan["id"]),
        "message": (
            f"Adherence monitoring started for {medication}. "
            "Check-ins scheduled for day 3 and day 7."
        ),
    }


def _fetch_check_ins(plan_id: str) -> list:
    full = get_adherence_plan(plan_id)
    return full.get("check_ins", []) if full else []


def process_check_in(
    check_in_id: str, response: str, side_effect_reported: bool
) -> dict:
    updated = submit_check_in(check_in_id, response, side_effect_reported)
    if not updated:
        return {"status": "error", "message": "Check-in not found"}

    triage = _perform_clinical_triage(response, side_effect_reported)
    empathetic = _optional_empathetic_reply(response, side_effect_reported)

    return {
        "status": "success",
        "check_in": updated,
        "side_effect_reported": side_effect_reported,
        "triage": triage,
        "empathetic_reply": empathetic,
    }


def _perform_clinical_triage(response: str, side_effect: bool) -> dict:
    """Analyze check-in for severity and clinical action using LLM."""
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        # Fallback logic
        severity = "MEDIUM" if side_effect else "LOW"
        action = "Review PGx profile" if side_effect else "Continue monitoring"
        return {
            "severity": severity,
            "action": action,
            "rationale": "Rule-based fallback used.",
        }

    try:
        completion = _groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a clinical pharmacogenomics triage agent. "
                        "Analyze the patient response and side-effect flag. "
                        "Return ONLY a JSON object with: severity (LOW, MEDIUM, HIGH, CRITICAL), "
                        "action (short clinical directive), and rationale (brief explanation). "
                        "Synthetic demo data only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Response: {response}. Side effect: {side_effect}",
                },
            ],
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.warning(f"Triage LLM failure: {e}", exc_info=True)
        return {
            "severity": "MEDIUM" if side_effect else "LOW",
            "action": "Clinician review recommended",
            "rationale": "Triage service error fallback.",
        }


def _optional_empathetic_reply(response: str, side_effect: bool) -> str | None:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        if side_effect:
            return (
                "Thank you for sharing that. Side effects can be difficult — "
                "your care team will review your profile and follow up soon."
            )
        return "Thank you for the update. Keep taking your medication as prescribed unless your clinician advises otherwise."

    try:
        completion = _groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an empathetic medication adherence assistant. "
                        "Reply in 1-2 warm, brief sentences. Synthetic demo only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Patient said: {response}. Side effect reported: {side_effect}",
                },
            ],
            model=GROQ_MODEL,
            max_tokens=100,
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.warning(f"Empathetic reply LLM failure: {e}")
        return None
```

## `agentic.py`

```python
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
```

## `analyst.py`

```python
from __future__ import annotations

import time

from pgx.patients import PatientRecord
from pgx.rules import RiskAssessment, assess_prescription


def analyze_risk(
    patient_id: str, medication: str, patient: PatientRecord | None
) -> tuple[RiskAssessment, str, int]:
    """Analyst Agent: deterministic pathway cross-reference."""
    start = time.perf_counter()
    assessment = assess_prescription(patient_id, medication, patient=patient)
    elapsed = int((time.perf_counter() - start) * 1000)

    if patient:
        phenotype = patient["cyp_profiles"][0]["phenotype"]
        summary = (
            f"Cross-referenced {medication} against {phenotype} — "
            f"risk level {assessment.risk_level.value}."
        )
    else:
        summary = assessment.risk_summary

    return assessment, summary, elapsed
```

## `bioinformatics_adapter.py`

```python
from __future__ import annotations

import hashlib
import time
from typing import Any


def simulate_folding_energy(sequence: str) -> float:
    """Simulate a MFE (Minimum Free Energy) calculation for RNA folding."""
    # Deterministic but pseudo-random energy based on sequence
    seed = hashlib.sha256(sequence.encode("utf-8")).hexdigest()
    base_energy = -20.0 - (int(seed[:4], 16) % 30)
    # Penalize GC content imbalance
    gc = (sequence.count("G") + sequence.count("C")) / len(sequence) if sequence else 0.5
    penalty = abs(gc - 0.52) * 50
    return round(base_energy + penalty, 2)


def simulate_homology_search(sequence: str) -> list[dict[str, Any]]:
    """Simulate a BLAST-like homology search for off-target risks."""
    # Deterministic mock results
    if "AAAAA" in sequence:
        return [{"target": "Poly-A binding protein region", "identity": 0.85, "e_value": 1e-5}]
    return []


def simulate_immunogenicity_score(sequence: str) -> float:
    """Simulate a predicted immunogenicity score."""
    # Simple heuristic for demo
    motifs = ("UGUGU", "GUCCUUCAA", "UGU")
    count = sum(sequence.count(m) for m in motifs)
    return min(1.0, count * 0.15)
```

## `challenger.py`

```python
from __future__ import annotations

import time

from models import AuditEvent, OverrideRequirement
from pgx.rules import RiskAssessment, RiskLevel


def challenge_decision(
    medication: str,
    phenotype: str,
    assessment: RiskAssessment,
    evidence_sources: list[str],
) -> tuple[list[AuditEvent], OverrideRequirement, list[str], str, str, int, float]:
    """Safety Challenge Agent: stress-test the proposed decision before release."""
    start = time.perf_counter()

    audit = [
        AuditEvent(
            stage="identity_and_genotype",
            decision="pass" if phenotype != "Unknown" else "needs_review",
            rationale=(
                f"CYP phenotype available: {phenotype}."
                if phenotype != "Unknown"
                else "No CYP phenotype available for patient."
            ),
            requires_human_review=phenotype == "Unknown",
        ),
        AuditEvent(
            stage="evidence_grounding",
            decision="pass" if evidence_sources else "needs_review",
            rationale=(
                f"Decision grounded in {', '.join(evidence_sources)}."
                if evidence_sources
                else "No local evidence source matched the case."
            ),
            requires_human_review=not evidence_sources,
        ),
    ]

    high_risk = assessment.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    audit.append(
        AuditEvent(
            stage="safety_challenge",
            decision="block" if high_risk else "approve_with_monitoring",
            rationale=(
                "Severe PGx mismatch detected; dispensing should be blocked unless an override is documented."
                if high_risk
                else "No severe PGx mismatch detected by the deterministic rule engine."
            ),
            requires_human_review=high_risk,
        )
    )

    override = OverrideRequirement(
        required=high_risk,
        reason=(
            "Critical/high PGx risk requires clinician override documentation."
            if high_risk
            else "No override required by the current PGx rule set."
        ),
        required_fields=[
            "clinician_id",
            "risk_benefit_rationale",
            "patient_counseling_attestation",
            "monitoring_plan",
        ]
        if high_risk
        else [],
    )

    if high_risk:
        actions = [
            "Hold dispensing until clinician review is documented.",
            f"Switch to {assessment.recommended_alternative or 'a non-CYP2D6-dependent alternative'} if clinically appropriate.",
            "Record patient counseling and monitoring plan before release.",
        ]
        verdict = "blocked_pending_override"
        summary = "Challenge agent upheld the block and generated override controls."
        confidence = 0.93 if evidence_sources else 0.78
    elif assessment.flagged:
        actions = [
            "Require clinician review before dispensing.",
            "Use lowest effective dose and monitor response within 72 hours.",
        ]
        verdict = "review_required"
        summary = "Challenge agent confirmed a moderate risk review path."
        confidence = 0.84
    else:
        actions = [
            "Proceed with standard monitoring.",
            "Offer adherence monitoring after dispensing.",
        ]
        verdict = "approved_with_monitoring"
        summary = "Challenge agent found no blocking PGx safety issue."
        confidence = 0.82

    elapsed = int((time.perf_counter() - start) * 1000)
    return audit, override, actions, verdict, summary, elapsed, confidence
```

## `critic.py`

```python
from __future__ import annotations

import time

from pgx.rules import RiskAssessment, RiskLevel


def critique_prescription(assessment: RiskAssessment) -> tuple[RiskAssessment, str, int]:
    """Critic Agent: confirm flag and safe alternative for severe mismatches."""
    start = time.perf_counter()

    if assessment.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        summary = (
            f"PRESCRIPTION BLOCKED — {assessment.risk_level.value.upper()} risk. "
            f"Recommend: {assessment.recommended_alternative or 'clinical review'}."
        )
    elif assessment.flagged:
        summary = (
            f"Prescription flagged ({assessment.risk_level.value}). "
            "Physician override requires documented rationale."
        )
    else:
        summary = "No PGx contraindication. Prescription may proceed with standard monitoring."

    elapsed = int((time.perf_counter() - start) * 1000)
    return assessment, summary, elapsed
```

## `generative.py`

```python
from __future__ import annotations

import hashlib
import time
from typing import Any

BALANCED_CODONS = (
    "GCU",
    "GAA",
    "CAA",
    "UGG",
    "AUC",
    "GAC",
    "AAA",
    "CGU",
    "UAC",
    "CCA",
)
LOW_GC_CODONS = ("AAU", "AUA", "UUA", "CAA", "GAA", "UAU", "AUC", "AAA")


def design_mrna_therapy(
    patient_profile: dict | None,
    target_disease: str,
    feedback: str | None = None,
) -> tuple[str, str, int]:
    """
    The Generative Agent (The Designer)
    Drafts the actual biological code (mRNA sequence) targeting the patient's disease.
    """
    start = time.time()
    
    phenotype = "Unknown"
    if (
        patient_profile
        and "cyp_profiles" in patient_profile
        and patient_profile["cyp_profiles"]
    ):
        phenotype = patient_profile["cyp_profiles"][0]["phenotype"]
    
    # Mocking base structural generation of an mRNA sequence based on constraints
    sequence = "AUG" + "GCA" * 15 + "UAA"
    
    rationale = (
        f"Drafted candidate mRNA sequence for {target_disease} optimized "
        f"for {phenotype} metabolizer. "
    )
    
    if feedback:
        rationale += f"Incorporated previous validation feedback: {feedback}."
        # Slightly alter the sequence to mock a deterministic change based on feedback
        sequence = "AUG" + "GCC" * 15 + "UAA"
        
    duration_ms = int((time.time() - start) * 1000)
    
    return sequence, rationale, duration_ms


def _stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _patient_phenotype(patient_profile: dict[str, Any] | None) -> str:
    if patient_profile and patient_profile.get("cyp_profiles"):
        return patient_profile["cyp_profiles"][0].get("phenotype", "Unknown")
    return "Unknown"


def design_research_mrna_candidate(
    patient_profile: dict[str, Any] | None,
    target_disease: str,
    evidence_bundle: dict[str, Any],
    *,
    iteration: int,
    revision_hints: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Create a deterministic simulated mRNA candidate for research review."""
    start = time.perf_counter()
    hints = revision_hints or []
    phenotype = _patient_phenotype(patient_profile)
    sources = evidence_bundle.get("sources", [])
    use_low_gc = any("gc" in hint.lower() for hint in hints)
    codon_pool = LOW_GC_CODONS if use_low_gc else BALANCED_CODONS

    patient_id = patient_profile.get("id") if patient_profile else "unknown"
    seed = f"{patient_id}:{target_disease}:{iteration}:{'|'.join(hints)}"
    offset = _stable_index(seed, len(codon_pool))
    body_codons = [
        codon_pool[(offset + index) % len(codon_pool)]
        for index in range(18)
    ]
    sequence = "AUG" + "".join(body_codons) + "UAA"
    sequence_hash = hashlib.sha256(sequence.encode("utf-8")).hexdigest()[:12]
    candidate_id = f"therapy-cand-{sequence_hash}-{iteration}"

    constraints = [
        "research simulation only",
        "RNA alphabet only",
        "AUG start codon",
        "terminal stop codon",
        "no intentional internal stop codons",
        "deterministic validation required",
        "human review required",
    ]
    if hints:
        constraints.extend(f"revision: {hint}" for hint in hints)

    candidate = {
        "candidate_id": candidate_id,
        "iteration": iteration,
        "modality": "simulated_mrna",
        "sequence": sequence,
        "design_constraints": constraints,
        "rationale": (
            f"Drafted a simulated mRNA candidate for {target_disease} using "
            f"patient phenotype context ({phenotype}) and retrieved research "
            f"evidence from {', '.join(sources) if sources else 'no sources'}."
        ),
        "evidence_refs": sources,
    }
    elapsed = int((time.perf_counter() - start) * 1000)
    return candidate, elapsed
```

## `knowledge.py`

```python
from __future__ import annotations

import os
import time
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from config import GROQ_MODEL

try:
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def _load_documents() -> list[tuple[str, str]]:
    documents: list[tuple[str, str]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        documents.append((path.name, path.read_text(encoding="utf-8")))
    return documents


def _score_document(text: str, medication: str, phenotype: str, risk_level: str) -> int:
    haystack = text.lower()
    terms = {
        medication.lower(),
        phenotype.lower(),
        phenotype.lower().replace("-", ""),
        risk_level.lower(),
        "cyp2d6",
        "opioid",
    }
    return sum(1 for term in terms if term and term in haystack)


def _extract_relevant_lines(text: str, medication: str, phenotype: str) -> list[str]:
    terms = [
        medication.lower(),
        phenotype.lower(),
        phenotype.lower().replace("-", ""),
        "cyp2d6",
        "recommendation",
        "clinical risk",
    ]
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("*").strip()
        if not line or line.startswith("#"):
            continue
        lower = line.lower().replace("-", "")
        if any(term.replace("-", "") in lower for term in terms):
            lines.append(line)
        if len(lines) >= 3:
            break
    return lines


def retrieve_clinical_evidence(
    medication: str, phenotype: str, risk_level: str
) -> tuple[str | None, int, list[str]]:
    """
    Knowledge Agent: retrieve source-backed guidance from local clinical notes.
    Task 4: Scoped ReAct.
    """
    start = time.perf_counter()
    
    # Reasoning Step (Internal)
    reasoning = f"Evaluating if local knowledge for {medication} + {phenotype} is sufficient..."
    
    documents = _load_documents()
    ranked = sorted(
        (
            (_score_document(text, medication, phenotype, risk_level), name, text)
            for name, text in documents
        ),
        reverse=True,
    )
    relevant = [(name, text) for score, name, text in ranked if score > 0][:3]
    sources = [name for name, _ in relevant]

    if not relevant:
        # ReAct Action: Simulate external search when local data is missing
        reasoning += " [ACTION] Local files insufficient. Querying external medical database (PubMed/PharmGKB mock)..."
        external_mock = (
            f"External Search Result: Case studies suggest {medication} should be used with extreme caution "
            f"in {phenotype} patients even without explicit CPIC guidelines. Monitor for metabolic compensation."
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        return f"{reasoning}\n\n{external_mock}", elapsed, ["external_medical_db"]

    if _groq is not None and os.environ.get("GROQ_API_KEY"):
        context = "\n\n".join(
            f"--- SOURCE: {name} ---\n{text}" for name, text in relevant
        )
        try:
            completion = _groq.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a clinical evidence extraction agent. "
                            "Use only the supplied source text. Return concise "
                            "evidence for a prescribing clinician. "
                            "MANDATORY: You MUST start your response with the exact name of the source file you are quoting from (e.g., 'Source: cpic_opioid_guidelines.md')."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Medication: {medication}\n"
                            f"Phenotype: {phenotype}\n"
                            f"Risk Level: {risk_level}\n\n"
                            f"{context}"
                        ),
                    },
                ],
                model=GROQ_MODEL,
                max_tokens=260,
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            return completion.choices[0].message.content, elapsed, sources
        except Exception as e:
            logger.error(f"Knowledge agent LLM call failed: {e}")
            pass

    snippets: list[str] = []
    for source, text in relevant:
        lines = _extract_relevant_lines(text, medication, phenotype)
        if lines:
            snippets.append(f"{source}: {' '.join(lines)}")

    elapsed = int((time.perf_counter() - start) * 1000)
    return "\n".join(snippets) if snippets else None, elapsed, sources
```

## `memory.py`

```python
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from datetime import UTC, datetime

from dotenv import load_dotenv

from config import GROQ_MODEL
from db.supabase import list_check_ins_for_patient, list_evaluations

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

def summarize_history(patient_id: str, current_medication: str) -> tuple[str, int, float]:
    """
    Memory Agent: analyzes previous evaluations AND check-ins to find clinical trends.
    Task 1: Closed-Loop Feedback.
    """
    start = time.perf_counter()
    
    # 1. Fetch data from Supabase
    history = list_evaluations(patient_id, limit=5)
    check_ins = list_check_ins_for_patient(patient_id, limit=3)
    
    # 2. Format Context
    eval_context = "\n".join([
        f"- {h.get('created_at', '')[:10]}: {h.get('medication')} (Flagged: {h.get('flagged')}, Risk: {h.get('risk_level')})"
        for h in history
    ])
    
    checkin_context = "\n".join([
        f"- Patient reported side effect on {c.get('adherence_plans', {}).get('medication')}: '{c.get('response')}'"
        for c in check_ins if c.get("side_effect_reported")
    ])

    full_context = f"PRESCRIBING HISTORY:\n{eval_context if eval_context else 'None'}\n\nREAL-WORLD ADHERENCE FEEDBACK:\n{checkin_context if checkin_context else 'No side effects reported in recent check-ins.'}"

    # 3. Determine Summary (LLM or Heuristic)
    summary = ""
    confidence = 0.7
    
    if not history and not check_ins:
        summary = "First recorded clinical encounter for this patient."
        confidence = 1.0
    elif _groq and os.environ.get("GROQ_API_KEY"):
        try:
            prompt = (
                f"Analyze the clinical history for a patient.\n"
                f"Current proposed drug: {current_medication}\n\n"
                f"{full_context}\n\n"
                "Provide a 1-sentence trend summary. Focus on identifying if previous prescriptions failed or caused reported side effects.\n"
            )
            completion = _groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a clinical history auditor specialized in pharmacogenomics."},
                    {"role": "user", "content": prompt}
                ],
                model=GROQ_MODEL,
                max_tokens=100
            )
            summary = completion.choices[0].message.content
            confidence = 0.95
        except Exception as e:
            logger.error(f"Memory agent trend summary LLM call failed: {e}")
            pass

    if not summary:
        # Fallback to heuristic
        past_meds = [h.get("medication") for h in history]
        if current_medication in past_meds:
            summary = f"Repeated evaluation for {current_medication}."
        else:
            summary = f"Patient has {len(history)} evaluations and {len(check_ins)} recent check-ins."
    
    # 4. CRITICAL: Sync to Obsidian Vault (Moved outside conditional)
    _write_to_vault(patient_id, current_medication, summary, full_context)
        
    elapsed = int((time.perf_counter() - start) * 1000)
    return summary, elapsed, confidence

def _write_to_vault(patient_id: str, med: str, summary: str, history: str):
    """
    Writes a persistent clinical note to the Obsidian vault using an atomic write strategy.
    Fixed Bug #12 (Silent Swallowing) and Bug #15 (Race Condition).
    """
    # Ensure we find the vault folder relative to the script location
    base_dir = os.environ.get("VAULT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault"))
    vault_dir = os.path.join(base_dir, "patients")
    file_path = os.path.join(vault_dir, f"{patient_id}.md")
    
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    note_content = (
        f"## Evaluation: {timestamp} (UTC)\n"
        f"- **Medication:** {med}\n"
        f"- **Trend Summary:** {summary}\n"
        f"\n### Historical Audit Trail\n{history}\n"
        f"---\n\n"
    )
    
    try:
        os.makedirs(vault_dir, exist_ok=True)
        
        # Atomic Write Strategy: Write to a temporary file in the same directory, then rename.
        # This prevents partial writes if the server crashes and avoids race conditions.
        with tempfile.NamedTemporaryFile(mode='w', dir=vault_dir, delete=False, encoding='utf-8', suffix='.tmp') as tmp_file:
            # Fixed Bug #3.9: Prevent vault file explosion by limiting to last 10 entries
            entries = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as original:
                    content = original.read()
                    # Split by the separator used in note_content
                    entries = content.split("---\n\n")
                    # Remove empty last element if exists
                    if entries and not entries[-1].strip():
                        entries.pop()

            # Add the new entry to the front or back
            entries.append(note_content.strip())

            # Keep only the last 10
            recent_entries = entries[-10:]

            # Join and write
            tmp_file.write("\n\n---\n\n".join(recent_entries) + "\n\n---\n\n")
            temp_name = tmp_file.name

        
        # Atomic replacement
        shutil.move(temp_name, file_path)
        logger.info(f"Vault synchronized atomically: {file_path}", extra={"patient_id": patient_id})
        
    except Exception as e:
        # Fixed Bug #12: No more silent swallowing. Log properly for DevOps.
        logger.error(
            "CRITICAL: Vault synchronization failed",
            extra={
                "patient_id": patient_id,
                "error": str(e)
            },
            exc_info=True
        )
```

## `orchestrator.py`

```python
from __future__ import annotations

from agents.agentic import orchestrate

```

## `policy_enforcer.py`

```python
from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

from config import GROQ_MODEL

import logging
logger = logging.getLogger(__name__)

def enforce_policy(medication: str, risk_level: str, rationale: str) -> tuple[str, str, int]:
    """
    Policy Enforcement Skill:
    1. Reads the local 'Override and Audit Policy' from the Vault.
    2. Compares the current prescription risk against clinic rules.
    3. Returns a formal compliance verdict.
    """
    start = time.perf_counter()
    
    # 1. Resolve Vault Path
    base_dir = os.environ.get("VAULT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault"))
    policy_path = os.path.join(base_dir, "clinical_logic", "Override_and_Audit_Policy.md")
    
    # 2. Read Local Policy
    try:
        with open(policy_path, encoding="utf-8") as f:
            policy_text = f.read()
    except Exception as e:
        logger.warning(f"Could not read local policy file: {e}. Using default.")
        policy_text = "Default Clinic Policy: All HIGH/CRITICAL risks require clinical justification."

    # 3. Use LLM as the 'Enforcer' using the Policy as context
    verdict = None
    analysis = None

    if _groq and os.environ.get("GROQ_API_KEY"):
        try:
            prompt = (
                f"You are the Clinical Compliance Officer for this health system.\n"
                f"Your task is to enforce the following local policy:\n\n"
                f"--- LOCAL POLICY ---\n{policy_text}\n\n"
                f"--- CURRENT CASE ---\n"
                f"Drug: {medication}\n"
                f"Calculated Risk: {risk_level}\n"
                f"Critic Rationale: {rationale}\n\n"
                "Return a 'Compliance Verdict' (APPROVED, BLOCKED, or CONDITIONAL) and a brief reasoning."
            )
            
            completion = _groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a medical compliance officer. Be strict and refer only to the provided policy."},
                    {"role": "user", "content": prompt}
                ],
                model=GROQ_MODEL,
                max_tokens=150
            )
            raw_output = completion.choices[0].message.content
            # Simple parsing for verdict
            if "APPROVED" in raw_output.upper(): verdict = "APPROVED"
            elif "BLOCKED" in raw_output.upper(): verdict = "BLOCKED"
            else: verdict = "CONDITIONAL"
            analysis = raw_output
        except Exception as e:
            logger.error(f"Policy Enforcer LLM call failed: {e}")
            
    if verdict is None:
        # Heuristic fallback
        if risk_level.upper() in ["CRITICAL", "HIGH"]:
            verdict = "BLOCKED"
            analysis = "Automatic block: High-risk prescribing requires manual override per clinic policy."
        else:
            verdict = "APPROVED"
            analysis = "Meets standard safety thresholds."

    elapsed = int((time.perf_counter() - start) * 1000)
    return verdict, analysis, elapsed
```

## `reporter.py`

```python
from __future__ import annotations

import os
import time
import logging
from typing import Any
from dotenv import load_dotenv
from models import EvaluationResponse
from config import GROQ_MODEL

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

def generate_clinical_note(evaluation_input: Any) -> str:
    """Generate a structured EHR-ready clinical note from an evaluation."""
    
    # FORCE conversion to Pydantic model to prevent 'dict' attribute errors
    try:
        if isinstance(evaluation_input, dict):
            evaluation = EvaluationResponse(**evaluation_input)
        else:
            evaluation = evaluation_input
    except Exception as e:
        return f"CRITICAL ERROR: Failed to parse evaluation data. {e}"

    # Enable LLM notes only if configured
    enable_llm = os.environ.get("ENABLE_LLM_NOTES", "").lower() == "true"
    
    if _groq is None or not enable_llm:
        return _generate_fallback_note(evaluation)

    try:
        patient = evaluation.patient
        medication = evaluation.medication
        risk_level = evaluation.risk_level
        risk_summary = evaluation.risk_summary
        rationale = evaluation.alternative_rationale
        alternative = evaluation.recommended_alternative or "None required"
        cpic_level = evaluation.cpic_level
        
        display_name = patient.display_name if patient else "Unknown Patient"
        age = patient.age if patient else "N/A"
        sex = patient.sex if patient else "N/A"
        indication = patient.indication if patient else "N/A"
        
        # Determine relevant gene/phenotype
        relevant_gene = "CYP2D6"
        phenotype = "Unknown"
        
        if patient and patient.cyp_profiles:
            for profile in patient.cyp_profiles:
                if profile.gene in risk_summary or any(profile.gene in p for p in evaluation.pathways):
                    relevant_gene = profile.gene
                    phenotype = profile.phenotype
                    break
            else:
                relevant_gene = patient.cyp_profiles[0].gene
                phenotype = patient.cyp_profiles[0].phenotype

        prompt = (
            f"Generate a professional, structured EHR clinical note for a pharmacogenomic (PGx) consultation.\n\n"
            f"PATIENT DATA:\n"
            f"- Name: {display_name}\n"
            f"- Age/Sex: {age} / {sex}\n"
            f"- Indication: {indication}\n\n"
            f"PGx FINDINGS:\n"
            f"- Gene: {relevant_gene}\n"
            f"- Phenotype: {phenotype}\n"
            f"- Proposed Drug: {medication}\n"
            f"- CPIC Evidence Level: {cpic_level}\n\n"
            f"EVALUATION:\n"
            f"- Risk Level: {risk_level.upper()}\n"
            f"- Summary: {risk_summary}\n"
            f"- Recommendation: {rationale}\n"
            f"- Alternative: {alternative}\n\n"
            "REQUIRED FORMAT:\n"
            "1. SUBJECTIVE: Brief mention of proposed therapy and indication.\n"
            "2. ASSESSMENT: Detail the PGx genotype/phenotype implications for this specific drug.\n"
            "3. PLAN: Clear directive on whether to proceed, adjust dose, or switch to the recommended alternative.\n\n"
            "Tone: Professional, objective, and concise. Use medical terminology."
        )

        completion = _groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Senior Clinical Pharmacogeneticist. Your task is to provide a structured, formal EHR documentation entry."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=GROQ_MODEL,
            max_tokens=600,
            temperature=0.2
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.warning(f"Note generation LLM failure: {e}", exc_info=True)
        return _generate_fallback_note(evaluation)

def _generate_fallback_note(eval: EvaluationResponse) -> str:
    p = eval.patient
    display_name = p.display_name if p else "N/A"
    indication = p.indication if p else "unspecified"
    
    relevant_gene = "CYP2D6"
    pheno = "Unknown"
    
    if p and p.cyp_profiles:
        for profile in p.cyp_profiles:
            if profile.gene in eval.risk_summary:
                relevant_gene = profile.gene
                pheno = profile.phenotype
                break
        else:
            relevant_gene = p.cyp_profiles[0].gene
            pheno = p.cyp_profiles[0].phenotype

    actions_text = "\n".join([f"- {a}" for a in eval.next_best_actions])
    date_str = time.strftime("%Y-%m-%d")
    
    return f"""CLINICAL PHARMACOGENOMIC CONSULTATION
-------------------------------------------
PATIENT: {display_name}
DATE: {date_str}

SUBJECTIVE:
Evaluation of proposed therapy with {eval.medication} for indication of {indication}.

ASSESSMENT:
Pharmacogenomic testing for {relevant_gene} reveals a {pheno.upper()} phenotype.
Clinical Risk: {eval.risk_level.upper()}
Implication: {eval.risk_summary}
Evidence Level: CPIC {eval.cpic_level.upper()}

PLAN:
{f"▶ SWITCH to {eval.recommended_alternative}. " if eval.recommended_alternative else "▶ PROCEED with standard dosing as per protocol. "}
Rationale: {eval.alternative_rationale}

NEXT STEPS:
{actions_text if actions_text else "- Monitor for clinical efficacy and adverse reactions."}

Electronically Signed: GenomicLens Orchestrator Agent v2.0
"""
```

## `research.py`

```python
from __future__ import annotations

import time

from db.supabase import get_patient_by_id
from exceptions import InvalidPhenotypeError, PatientNotFoundError
from pgx.patients import PatientRecord


def research_patient(patient_id: str) -> tuple[PatientRecord | None, str, int]:
    """Research Agent: load n-of-1 phenotype from Supabase or seed fallback."""
    start = time.perf_counter()
    patient = get_patient_by_id(patient_id)
    elapsed = int((time.perf_counter() - start) * 1000)

    if patient is None:
        # Halt the pipeline immediately and return a typed 404 error
        raise PatientNotFoundError(patient_id)

    # Fixed Bug #3: Safe array access for cyp_profiles
    if not patient.get("cyp_profiles"):
        raise InvalidPhenotypeError(patient_id, gene="ANY")

    profile = patient["cyp_profiles"][0]
    phenotype = profile["phenotype"]
    gene = profile["gene"]
    
    summary = (
        f"Retrieved FHIR-linked profile for {patient['display_name']}: "
        f"{gene} {phenotype}."
    )
    return patient, summary, elapsed
```

## `therapy_orchestrator.py`

```python
from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.generative import design_research_mrna_candidate
from agents.research import research_patient
from agents.therapy_rag import retrieve_therapy_evidence
from agents.validation import validate_research_mrna_candidate
from models import (
    AgentStep,
    AuditEvent,
    HumanGate,
    TherapyCandidate,
    TherapyEvidenceBundle,
    TherapyGenerationResponse,
    TherapyValidationResult,
)


class TherapyGraphState(TypedDict, total=False):
    therapy_request_id: str
    patient_id: str
    target_disease: str
    max_iterations: int
    patient: dict[str, Any] | None
    patient_context: dict[str, Any] | None
    evidence_bundle: dict[str, Any] | None
    target_profile: dict[str, Any] | None
    candidate_history: list[dict[str, Any]]
    active_candidate: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    critique: dict[str, Any] | None
    revision_hints: list[str]
    iteration: int
    status: str
    agent_steps: list[AgentStep]
    audit_events: list[AuditEvent]
    safety_notes: list[str]
    clinical_narrative: str


def _step(
    agent: str,
    status: str,
    summary: str,
    duration_ms: int,
    confidence: float,
    evidence_refs: list[str] | None = None,
) -> AgentStep:
    return AgentStep(
        agent=agent,
        status=status,
        summary=summary,
        duration_ms=duration_ms,
        confidence=confidence,
        evidence_refs=evidence_refs or [],
    )


def _audit(
    stage: str,
    decision: str,
    rationale: str,
    *,
    human: bool = False,
) -> AuditEvent:
    return AuditEvent(
        stage=stage,
        decision=decision,
        rationale=rationale,
        requires_human_review=human,
    )


def _append_step(state: TherapyGraphState, step: AgentStep) -> list[AgentStep]:
    return [*state.get("agent_steps", []), step]


def _append_audit(state: TherapyGraphState, event: AuditEvent) -> list[AuditEvent]:
    return [*state.get("audit_events", []), event]


def request_guardrails_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    target = state["target_disease"].strip()
    warnings = [
        "Research simulation only; not clinically validated.",
        "No autonomous treatment, dosing, or manufacturing use.",
    ]
    downstream_terms = ("dose", "inject", "manufacturing-ready")
    if any(term in target.lower() for term in downstream_terms):
        warnings.append(
            "Request language includes downstream-use terms; final review gate "
            "will remain locked."
        )

    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "target_disease": target,
        "safety_notes": warnings,
        "agent_steps": _append_step(
            state,
            _step(
                "RequestGuardrails",
                "complete",
                (
                    "Request constrained to a research simulation with no "
                    "autonomous clinical use."
                ),
                elapsed,
                1.0,
                ["n_of_1_research_policy"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "request_guardrails",
                "pass",
                "The request can proceed as a research simulation only.",
                human=True,
            ),
        ),
    }


def patient_context_node(state: TherapyGraphState) -> dict[str, Any]:
    patient, summary, elapsed = research_patient(state["patient_id"])
    patient_context = {
        "patient_id": patient["id"],
        "display_name": patient["display_name"],
        "indication": patient["indication"],
        "cyp_profiles": patient["cyp_profiles"],
        "clinical_history_summary": summary,
        "safety_constraints": [
            "Use patient phenotype as context only.",
            "Do not infer dosing or treatment authorization.",
        ],
    }
    return {
        "patient": patient,
        "patient_context": patient_context,
        "agent_steps": _append_step(
            state,
            _step(
                "PatientContext",
                "complete",
                summary,
                elapsed,
                0.95,
                ["patient_profile"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "patient_context",
                "pass",
                f"Loaded patient context for {patient['id']}.",
            ),
        ),
    }


def evidence_rag_node(state: TherapyGraphState) -> dict[str, Any]:
    evidence, elapsed = retrieve_therapy_evidence(
        state["target_disease"],
        state["patient_context"] or {},
    )
    confidence = {"high": 0.9, "moderate": 0.74, "low": 0.35}.get(
        evidence["evidence_quality"],
        0.5,
    )
    return {
        "evidence_bundle": evidence,
        "agent_steps": _append_step(
            state,
            _step(
                "DiseaseTargetRAG",
                "complete" if evidence["sources"] else "blocked",
                evidence["target_rationale"],
                elapsed,
                confidence,
                evidence["sources"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "evidence_retrieval",
                "pass" if evidence["sources"] else "block",
                (
                    f"Retrieved evidence sources: {', '.join(evidence['sources'])}."
                    if evidence["sources"]
                    else "No source-backed therapy evidence was retrieved."
                ),
                human=evidence["evidence_quality"] != "high",
            ),
        ),
    }


def target_selection_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    evidence = state["evidence_bundle"] or {}
    patient_context = state["patient_context"] or {}
    
    # Improved target selection using evidence bundle
    target_rationale = evidence.get("target_rationale", "No evidence summary.")
    evidence_quality = evidence.get("evidence_quality", "low")
    sources = evidence.get("sources", [])
    
    # Determine confidence based on evidence quality
    confidence = {"high": 0.92, "moderate": 0.78, "low": 0.25}.get(evidence_quality, 0.15)
    
    # Architecture: Refuse target selection if evidence is too weak
    status = "complete"
    if not sources or evidence_quality == "low":
        status = "blocked"
        rationale = (
            "Target selection blocked: insufficient research evidence quality "
            f"({evidence_quality}) to proceed with a simulated candidate design."
        )
    else:
        rationale = (
            f"Selected a simulated therapeutic target for {state['target_disease']} "
            f"based on {evidence_quality}-quality research evidence. "
            f"Target rationale: {target_rationale}"
        )

    target_profile = {
        "target_name": f"{state['target_disease']} research target",
        "target_type": "pathway" if "pathway" in target_rationale.lower() else "protein",
        "rationale": rationale,
        "evidence_refs": sources,
        "confidence": confidence,
    }
    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "target_profile": target_profile,
        "agent_steps": _append_step(
            state,
            _step(
                "TargetSelection",
                status,
                rationale,
                elapsed,
                confidence,
                sources,
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "target_selection",
                "pass" if status == "complete" else "block",
                rationale,
                human=True,
            ),
        ),
    }


def candidate_design_node(state: TherapyGraphState) -> dict[str, Any]:
    iteration = state.get("iteration", 0) + 1
    candidate, elapsed = design_research_mrna_candidate(
        state.get("patient"),
        state["target_disease"],
        state.get("evidence_bundle") or {},
        iteration=iteration,
        revision_hints=state.get("revision_hints", []),
    )
    history = [*state.get("candidate_history", []), candidate]
    return {
        "iteration": iteration,
        "active_candidate": candidate,
        "candidate_history": history,
        "revision_hints": [],
        "agent_steps": _append_step(
            state,
            _step(
                "CandidateDesign",
                "complete",
                f"Iteration {iteration}: {candidate['rationale']}",
                elapsed,
                0.82,
                candidate["evidence_refs"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "candidate_design",
                "pass",
                f"Generated {candidate['candidate_id']} for deterministic validation.",
                human=True,
            ),
        ),
    }


def validation_node(state: TherapyGraphState) -> dict[str, Any]:
    candidate = state["active_candidate"] or {}
    validation, elapsed = validate_research_mrna_candidate(
        candidate.get("sequence", "")
    )
    return {
        "validation_result": validation,
        "agent_steps": _append_step(
            state,
            _step(
                "InSilicoValidation",
                "approved" if validation["passed"] else "blocked",
                (
                    "Deterministic validation passed; candidate can move to "
                    "safety critique."
                    if validation["passed"]
                    else (
                        "Validation blocked candidate: "
                        f"{'; '.join(validation['blocked_reasons'])}"
                    )
                ),
                elapsed,
                0.9 if validation["passed"] else 0.62,
                ["deterministic_sequence_validator"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "in_silico_validation",
                "pass" if validation["passed"] else "block",
                (
                    f"Overall simulated risk score: {validation['overall_risk_score']}."
                ),
                human=True,
            ),
        ),
    }


def safety_critic_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    evidence = state.get("evidence_bundle") or {}
    validation = state.get("validation_result") or {}
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    unresolved = list(evidence.get("known_risks", []))

    if not evidence.get("sources"):
        verdict = "failed"
        summary = (
            "Critic blocked the workflow because no source-backed evidence "
            "was retrieved."
        )
    elif not validation.get("passed"):
        verdict = "revise" if iteration < max_iterations else "failed"
        summary = (
            "Critic requested revision using validation feedback."
            if verdict == "revise"
            else "Critic failed the workflow after maximum validation attempts."
        )
    else:
        verdict = "research_review_required"
        summary = "Critic accepted the candidate only for human-gated research review."

    critique = {
        "verdict": verdict,
        "summary": summary,
        "unresolved_risks": unresolved,
        "required_review_fields": [
            "reviewer_id",
            "research_rationale",
            "evidence_review_attestation",
            "safety_risk_acknowledgement",
        ],
        "confidence": 0.86 if verdict == "research_review_required" else 0.72,
    }
    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "critique": critique,
        "agent_steps": _append_step(
            state,
            _step(
                "SafetyCritic",
                "blocked" if verdict == "failed" else "review_required",
                summary,
                elapsed,
                critique["confidence"],
                evidence.get("sources", []),
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "safety_critic",
                verdict,
                summary,
                human=True,
            ),
        ),
    }


def revision_planner_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    validation = state.get("validation_result") or {}
    hints = validation.get("revision_hints") or [
        "Revise candidate using critic feedback."
    ]
    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "revision_hints": hints,
        "agent_steps": _append_step(
            state,
            _step(
                "RevisionPlanner",
                "complete",
                f"Prepared revision constraints: {'; '.join(hints)}",
                elapsed,
                0.8,
                ["validation_feedback"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "revision_planning",
                "retry",
                f"Retrying with constraints: {'; '.join(hints)}",
                human=True,
            ),
        ),
    }


def report_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    candidate = state["active_candidate"] or {}
    evidence = state["evidence_bundle"] or {}
    validation = state["validation_result"] or {}
    narrative = (
        f"Generated {candidate.get('candidate_id')} as a simulated n-of-1 mRNA "
        f"research candidate for {state['target_disease']}. Deterministic validation "
        f"returned risk score {validation.get('overall_risk_score')}; evidence sources "
        f"were {', '.join(evidence.get('sources', []))}. Human research review "
        "is required."
    )
    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "status": "research_review_required",
        "agent_steps": _append_step(
            state,
            _step(
                "HumanGate",
                "pending",
                "Candidate package is ready for human research review only.",
                elapsed,
                1.0,
                ["human_review"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "human_gate",
                "pending",
                "Researcher or clinician review required before downstream use.",
                human=True,
            ),
        ),
        "clinical_narrative": narrative,
    }


def failure_report_node(state: TherapyGraphState) -> dict[str, Any]:
    start = time.perf_counter()
    critique = state.get("critique") or {}
    validation = state.get("validation_result") or {}
    target_profile = state.get("target_profile") or {}
    
    reasons = validation.get("blocked_reasons") or []
    if not reasons and target_profile.get("confidence", 1.0) < 0.4:
        reasons.append(target_profile.get("rationale", "Insufficient evidence."))
    if not reasons:
        reasons = critique.get("unresolved_risks") or [
            "The workflow did not meet research simulation safety requirements."
        ]
        
    narrative = (
        f"N-of-1 research simulation failed for {state['target_disease']}. "
        f"Reason: {'; '.join(reasons)} Human review is required before retrying."
    )
    elapsed = int((time.perf_counter() - start) * 1000)
    return {
        "status": "failed",
        "agent_steps": _append_step(
            state,
            _step(
                "FailureReport",
                "blocked",
                narrative,
                elapsed,
                0.88,
                ["audit_trail"],
            ),
        ),
        "audit_events": _append_audit(
            state,
            _audit(
                "failure_report",
                "block",
                narrative,
                human=True,
            ),
        ),
        "clinical_narrative": narrative,
    }


def _route_after_critic(state: TherapyGraphState) -> str:
    critique = state.get("critique") or {}
    verdict = critique.get("verdict")
    if verdict == "research_review_required":
        return "report"
    if (
        verdict == "revise"
        and state.get("iteration", 0) < state.get("max_iterations", 3)
    ):
        return "revise"
    return "failure"


def _route_after_target_selection(state: TherapyGraphState) -> str:
    target_profile = state.get("target_profile") or {}
    if target_profile.get("confidence", 0) < 0.4:
        return "failure"
    return "candidate"


def _build_graph():
    graph = StateGraph(TherapyGraphState)
    graph.add_node("guardrails", request_guardrails_node)
    graph.add_node("patient_context", patient_context_node)
    graph.add_node("evidence_rag", evidence_rag_node)
    graph.add_node("target_selection", target_selection_node)
    graph.add_node("candidate_design", candidate_design_node)
    graph.add_node("validation", validation_node)
    graph.add_node("safety_critic", safety_critic_node)
    graph.add_node("revision_planner", revision_planner_node)
    graph.add_node("report", report_node)
    graph.add_node("failure_report", failure_report_node)

    graph.add_edge(START, "guardrails")
    graph.add_edge("guardrails", "patient_context")
    graph.add_edge("patient_context", "evidence_rag")
    graph.add_edge("evidence_rag", "target_selection")
    graph.add_conditional_edges(
        "target_selection",
        _route_after_target_selection,
        {
            "candidate": "candidate_design",
            "failure": "failure_report",
        },
    )
    graph.add_edge("candidate_design", "validation")
    graph.add_edge("validation", "safety_critic")
    graph.add_conditional_edges(
        "safety_critic",
        _route_after_critic,
        {
            "report": "report",
            "revise": "revision_planner",
            "failure": "failure_report",
        },
    )
    graph.add_edge("revision_planner", "candidate_design")
    graph.add_edge("report", END)
    graph.add_edge("failure_report", END)
    return graph.compile()


THERAPY_GRAPH = _build_graph()


def _logic_tree(state: TherapyGraphState) -> dict[str, Any]:
    evidence = state.get("evidence_bundle") or {}
    validation = state.get("validation_result") or {}
    critique = state.get("critique") or {}
    return {
        "node": "N-of-1 Research Simulation",
        "children": [
            {
                "node": "Evidence RAG",
                "detail": evidence.get("target_rationale", "No evidence summary."),
                "sources": evidence.get("sources", []),
            },
            {
                "node": "Candidate Design",
                "detail": (state.get("active_candidate") or {}).get(
                    "candidate_id",
                    "No candidate.",
                ),
                "iterations": state.get("iteration", 0),
            },
            {
                "node": "Validation",
                "detail": f"Risk score {validation.get('overall_risk_score')}",
                "passed": validation.get("passed", False),
            },
            {
                "node": "Critic",
                "detail": critique.get("summary", "No critique."),
                "verdict": critique.get("verdict"),
            },
            {
                "node": "Human Gate",
                "detail": (
                    "Researcher or clinician review required before downstream use."
                ),
                "flag": True,
            },
        ],
    }


def orchestrate_therapy_generation(
    patient_id: str,
    target_disease: str,
    max_iterations: int = 3,
) -> TherapyGenerationResponse:
    initial_state: TherapyGraphState = {
        "therapy_request_id": str(uuid.uuid4()),
        "patient_id": patient_id.upper(),
        "target_disease": target_disease,
        "max_iterations": max(1, min(max_iterations, 5)),
        "patient": None,
        "patient_context": None,
        "evidence_bundle": None,
        "target_profile": None,
        "candidate_history": [],
        "active_candidate": None,
        "validation_result": None,
        "critique": None,
        "revision_hints": [],
        "iteration": 0,
        "status": "running",
        "agent_steps": [],
        "audit_events": [],
        "safety_notes": [],
    }
    final_state = THERAPY_GRAPH.invoke(initial_state)
    candidate = final_state.get("active_candidate")
    evidence = final_state.get("evidence_bundle")
    validation = final_state.get("validation_result")
    candidate_history = [
        TherapyCandidate(**item)
        for item in final_state.get("candidate_history", [])
    ]
    final_candidate = TherapyCandidate(**candidate) if candidate else None
    validation_result = TherapyValidationResult(**validation) if validation else None
    evidence_bundle = TherapyEvidenceBundle(**evidence) if evidence else None
    human_gate = HumanGate(
        required=True,
        status="pending",
        reason="Researcher or clinician review required before downstream use.",
        required_fields=[
            "reviewer_id",
            "research_rationale",
            "evidence_review_attestation",
            "safety_risk_acknowledgement",
        ],
    )

    return TherapyGenerationResponse(
        status=final_state.get("status", "failed"),
        patient_id=patient_id.upper(),
        target_disease=target_disease,
        mrna_sequence=candidate.get("sequence") if candidate else None,
        toxicity_score=validation.get("overall_risk_score") if validation else None,
        iterations=final_state.get("iteration", 0),
        agent_steps=final_state.get("agent_steps", []),
        clinical_narrative=final_state.get(
            "clinical_narrative",
            "N-of-1 research simulation completed with no narrative.",
        ),
        therapy_request_id=final_state.get("therapy_request_id"),
        candidate_id=candidate.get("candidate_id") if candidate else None,
        final_candidate=final_candidate,
        candidate_history=candidate_history,
        validation_result=validation_result,
        evidence_bundle=evidence_bundle,
        evidence_sources=evidence_bundle.sources if evidence_bundle else [],
        safety_notes=final_state.get("safety_notes", []),
        audit_trail=final_state.get("audit_events", []),
        logic_tree=_logic_tree(final_state),
        human_gate=human_gate,
    )
```

## `therapy_rag.py`

```python
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

CORE_TERMS = {
    "mrna",
    "therapy",
    "target",
    "candidate",
    "sequence",
    "validation",
    "safety",
    "human",
    "review",
    "research",
    "simulation",
}


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2
    }


def _load_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts = [
            part.strip()
            for part in re.split(r"\n(?=## |\# )", text)
            if part.strip()
        ]
        for index, part in enumerate(parts):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.name}:{index + 1}",
                    "text": part,
                }
            )
    return chunks


def _score_chunk(chunk: dict[str, Any], query_terms: set[str]) -> int:
    chunk_terms = _tokenize(chunk["text"])
    source_terms = _tokenize(chunk["source"].replace("_", " "))
    overlap = len(query_terms & chunk_terms)
    core_overlap = len(CORE_TERMS & chunk_terms)
    source_overlap = len(query_terms & source_terms)
    return (overlap * 3) + core_overlap + source_overlap


def _snippet(text: str, limit: int = 360) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def retrieve_therapy_evidence(
    target_disease: str,
    patient_context: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Retrieve source-grounded context for the n-of-1 research workflow."""
    start = time.perf_counter()
    # Exclude very common terms from the "must-match" disease set
    stop_terms = {"disease", "research", "simulation", "therapy", "target", "patient", "clinical"}
    disease_terms = _tokenize(target_disease) - stop_terms
    
    phenotype_terms = {
        profile.get("phenotype", "")
        for profile in patient_context.get("cyp_profiles", [])
        if isinstance(profile, dict)
    }
    general_terms = _tokenize("mRNA therapy target validation safety human review research simulation")
    query_terms = _tokenize(target_disease) | _tokenize(patient_context.get("indication", "")) | _tokenize(" ".join(phenotype_terms)) | general_terms

    chunks = _load_chunks()
    ranked = []
    for chunk in chunks:
        score = _score_chunk(chunk, query_terms)
        # Bonus for specific disease-name overlap
        disease_overlap = len(disease_terms & _tokenize(chunk["text"])) if disease_terms else 0
        score += (disease_overlap * 20)
        if score > 0:
            ranked.append((score, chunk, disease_overlap))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:5]

    if not selected:
        return _low_quality_response(start)

    sources = sorted({chunk["source"] for _, chunk, _ in selected})
    total_disease_overlap = sum(d for _, _, d in selected)
    
    policy_present = any("n_of_1" in source for source in sources)
    
    # Logic: If a specific disease term was provided, it MUST be found in sources
    # to be considered moderate/high quality.
    if disease_terms and total_disease_overlap < 1:
        return _low_quality_response(start)
    
    if total_disease_overlap >= 3:
        evidence_quality = "high" if len(sources) >= 2 and policy_present else "moderate"
    elif total_disease_overlap >= 1 or not disease_terms:
        evidence_quality = "moderate"
    else:
        return _low_quality_response(start)

    elapsed = int((time.perf_counter() - start) * 1000)
    return (
        {
            "sources": sources,
            "target_rationale": (
                f"Retrieved {len(selected)} source chunks for {target_disease}. "
                "The evidence supports a simulated research candidate and "
                "requires human review."
            ),
            "known_risks": [
                "The candidate is not clinically validated.",
                "Sequence validation is deterministic but still a simulation.",
                "Disease-specific target evidence may be incomplete.",
            ],
            "open_questions": [
                "Is the target disease mechanism sufficiently documented?",
                "Does the reviewer accept the validation thresholds?",
            ],
            "evidence_quality": evidence_quality,
            "source_snippets": [
                {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                    "score": score,
                    "snippet": _snippet(chunk["text"]),
                }
                for score, chunk, _ in selected
            ],
        },
        elapsed,
    )


def _low_quality_response(start_time: float) -> tuple[dict[str, Any], int]:
    elapsed = int((time.perf_counter() - start_time) * 1000)
    return (
        {
            "sources": [],
            "target_rationale": (
                "No disease-specific evidence was retrieved. The system cannot "
                "reliably identify a therapeutic target for this indication."
            ),
            "known_risks": ["Insufficient source grounding for target selection."],
            "open_questions": ["Which reviewed disease mechanism supports this target?"],
            "evidence_quality": "low",
            "source_snippets": [],
        },
        elapsed,
    )
```

## `validation.py`

```python
from __future__ import annotations

import os
import random
import time
from typing import Any

# Use a frozenset for O(1) membership testing and clear semantic intent
SAFE_DRUGS = frozenset({
    "Duloxetine", "Pregabalin", "Prasugrel", "Ticagrelor",
    "Acetaminophen (scheduled)", "Sertraline", "Bupropion", "Ibuprofen"
})
RNA_ALPHABET = frozenset({"A", "U", "G", "C"})
STOP_CODONS = frozenset({"UAA", "UAG", "UGA"})

def validate_drug_safety(drug: str) -> tuple[bool, float, str, int]:
    """
    Validates the safety of a proposed drug using deterministic rules.
    """
    start = time.time()
    
    # If the drug is explicitly in our safe list, mark it safe. Otherwise, 0.8 toxicity.
    toxicity_score = 0.2 if drug in SAFE_DRUGS else 0.8
    duration_ms = int((time.time() - start) * 1000)
    
    if toxicity_score > 0.5:
        is_safe = False
        feedback = (
            f"{drug} failed safety validation "
            f"(mock toxicity score: {toxicity_score:.2f})."
        )
    else:
        is_safe = True
        feedback = (
            f"{drug} passed safety validation. "
            f"Toxicity score: {toxicity_score:.2f}."
        )

    return is_safe, toxicity_score, feedback, duration_ms

def validate_mrna_sequence(sequence: str) -> tuple[bool, float, str, int]:
    """
    The Validation Agent (The Safety Guardrail)
    Connects to deterministic, physics-based biological simulators.
    Runs 'in-silico' tests to see if the generated mRNA will fold correctly or be toxic.
    """
    start = time.time()

    # Mocking in-silico physics-based simulation
    # Fixed Remaining Issue: Allow deterministic overrides for testing
    mock_override = os.environ.get("MOCK_MRNA_TOXICITY")
    if mock_override is not None:
        try:
            toxicity_score = float(mock_override)
        except ValueError:
            toxicity_score = random.uniform(0.1, 0.9)
    else:
        toxicity_score = random.uniform(0.1, 0.9)
        
    duration_ms = int((time.time() - start) * 1000)

    # Set threshold at 0.5 to force occasional loops between generative and validation
    if toxicity_score > 0.5:
        is_safe = False
        feedback = (
            f"Sequence failed stability test with toxicity score {toxicity_score:.2f}. "
            "High probability of off-target binding. Redesign and optimize for lower "
            "free energy."
        )
    else:
        is_safe = True
        feedback = (
            "Sequence passed in-silico safety validation. "
            f"Toxicity score: {toxicity_score:.2f}. Folding structure stable."
        )

    return is_safe, toxicity_score, feedback, duration_ms


def _codons(sequence: str) -> list[str]:
    return [sequence[index:index + 3] for index in range(0, len(sequence), 3)]


def _gc_content(sequence: str) -> float:
    if not sequence:
        return 0.0
    return (sequence.count("G") + sequence.count("C")) / len(sequence)


def _repeat_risk(codons: list[str]) -> float:
    if not codons:
        return 1.0
    longest = 1
    current = 1
    for previous, current_codon in zip(codons, codons[1:], strict=False):
        if previous == current_codon:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest / len(codons)


def _check(
    name: str,
    passed: bool,
    score: float,
    detail: str,
    severity: str = "info",
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "score": max(0.0, min(1.0, score)),
        "detail": detail,
        "severity": severity,
    }


from agents.bioinformatics_adapter import (
    simulate_folding_energy,
    simulate_homology_search,
    simulate_immunogenicity_score,
)


def validate_research_mrna_candidate(sequence: str) -> tuple[dict[str, Any], int]:
    """Run deterministic checks and simulated bioinformatics for the n-of-1 research simulation."""
    start = time.perf_counter()
    normalized = sequence.upper().replace(" ", "").replace("\n", "")
    
    # Phase 4: Simulated Bioinformatics Integrations
    mfe = simulate_folding_energy(normalized)
    homology = simulate_homology_search(normalized)
    immunogenicity = simulate_immunogenicity_score(normalized)
    
    codons = _codons(normalized) if len(normalized) % 3 == 0 else []
    coding_codons = codons[1:-1] if len(codons) >= 2 else []
    internal_stop_count = sum(1 for codon in coding_codons if codon in STOP_CODONS)
    gc = _gc_content(normalized)
    repeat_risk = _repeat_risk(coding_codons)

    checks = [
        _check(
            "rna_alphabet",
            set(normalized).issubset(RNA_ALPHABET),
            1.0 if set(normalized).issubset(RNA_ALPHABET) else 0.0,
            "Sequence uses only A, U, G, and C.",
            "critical",
        ),
        _check(
            "reading_frame",
            len(normalized) >= 30 and len(normalized) % 3 == 0,
            1.0 if len(normalized) >= 30 and len(normalized) % 3 == 0 else 0.0,
            f"Sequence length is {len(normalized)} bases.",
            "critical",
        ),
        _check(
            "folding_stability",
            mfe <= -25.0,
            1.0 if mfe <= -25.0 else 0.5,
            f"Predicted MFE is {mfe} kcal/mol (threshold: -25.0).",
            "warning",
        ),
        _check(
            "homology_off_target",
            not homology,
            1.0 if not homology else 0.4,
            f"Detected {len(homology)} potential off-target homologies." if homology else "No high-identity homologies detected.",
            "warning",
        ),
        _check(
            "immunogenicity_risk",
            immunogenicity <= 0.4,
            1.0 - immunogenicity,
            f"Predicted immunogenicity score is {immunogenicity:.2f}.",
            "warning",
        ),
        _check(
            "start_codon",
            normalized.startswith("AUG"),
            1.0 if normalized.startswith("AUG") else 0.0,
            "Sequence starts with AUG.",
            "critical",
        ),
        _check(
            "terminal_stop",
            bool(codons and codons[-1] in STOP_CODONS),
            1.0 if codons and codons[-1] in STOP_CODONS else 0.0,
            "Sequence ends with a terminal stop codon.",
            "critical",
        ),
        _check(
            "internal_stop_codons",
            internal_stop_count == 0,
            1.0 if internal_stop_count == 0 else 0.0,
            f"Detected {internal_stop_count} internal stop codons.",
            "critical",
        ),
        _check(
            "gc_content",
            0.35 <= gc <= 0.70,
            1.0 - min(abs(gc - 0.52), 0.52),
            f"GC content is {gc:.2f}; accepted demo range is 0.35-0.70.",
            "warning",
        ),
        _check(
            "repeat_motif_risk",
            repeat_risk <= 0.30,
            1.0 - repeat_risk,
            f"Longest repeated codon run ratio is {repeat_risk:.2f}.",
            "warning",
        ),
    ]

    blocked_reasons = [
        check["detail"]
        for check in checks
        if not check["passed"] and check["severity"] == "critical"
    ]
    # Block on specific warnings for the research simulation
    if not checks[2]["passed"]: # folding
        blocked_reasons.append(checks[2]["detail"])
    if not checks[8]["passed"]: # gc
        blocked_reasons.append(checks[8]["detail"])

    revision_hints: list[str] = []
    if not checks[0]["passed"]:
        revision_hints.append("Use only RNA bases A, U, G, and C.")
    if not checks[1]["passed"]:
        revision_hints.append("Keep the sequence in-frame and at least 30 bases long.")
    if mfe > -25.0:
        revision_hints.append("Optimize sequence for higher folding stability (lower MFE).")
    if homology:
        revision_hints.append("Modify sequence to avoid known off-target homologies.")
    if immunogenicity > 0.4:
        revision_hints.append("Reduce immunogenic motif density.")
    if not checks[5]["passed"]:
        revision_hints.append("Add an AUG start codon.")
    if not checks[6]["passed"]:
        revision_hints.append("Add a valid terminal stop codon.")
    if internal_stop_count:
        revision_hints.append("Remove internal stop codons from the coding region.")
    if gc > 0.70:
        revision_hints.append("Reduce GC content.")
    elif gc < 0.35:
        revision_hints.append("Increase GC content.")
    if repeat_risk > 0.30:
        revision_hints.append("Diversify repeated codons.")

    failure_weight = sum(0.12 for check in checks if not check["passed"])
    risk_score = min(
        1.0,
        0.10
        + failure_weight
        + (repeat_risk * 0.15)
        + (immunogenicity * 0.20)
        + min(abs(gc - 0.52), 0.25),
    )
    passed = not blocked_reasons and risk_score <= 0.50
    elapsed = int((time.perf_counter() - start) * 1000)
    return (
        {
            "passed": passed,
            "overall_risk_score": round(risk_score, 2),
            "checks": checks,
            "blocked_reasons": blocked_reasons,
            "revision_hints": revision_hints,
            "validator_version": "1.4.2-research",
        },
        elapsed,
    )
```
