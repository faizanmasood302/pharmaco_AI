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
