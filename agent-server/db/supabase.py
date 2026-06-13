from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

from models import PatientIn, PatientOut
from pgx.patients import PATIENTS, PatientRecord, get_patient

logger = logging.getLogger(__name__)
# Load environment and define variables at module level
load_dotenv()
_url = (os.environ.get("SUPABASE_URL") or "").strip()
_key = (os.environ.get("SUPABASE_ANON_KEY") or "").strip()
_service_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

_client: Client | None = None
_admin_client: Client | None = None
_local_evaluations: dict[str, dict[str, Any]] = {}
_local_therapy_requests: dict[str, dict[str, Any]] = {}
_local_therapy_candidates: dict[str, list[dict[str, Any]]] = {}
_local_therapy_validation_results: dict[str, dict[str, Any]] = {}
_local_therapy_audit_events: dict[str, list[dict[str, Any]]] = {}

try:
    if _url and _key:
        _client = create_client(_url, _key)

        if _service_key:
            logger.info("Initializing admin client with Service Role Key")
            _admin_client = create_client(_url, _service_key)
        else:
            logger.warning(
                "Service Role Key missing; using anon client as fallback for admin tasks."
            )
            _admin_client = _client
    else:
        logger.error("SUPABASE_URL or SUPABASE_ANON_KEY is missing from environment")
except Exception as e:
    logger.error(f"Failed to initialize Supabase clients: {e}")
    _client = None
    _admin_client = None


def list_medications() -> list[dict[str, Any]]:
    """List all medications from the database."""
    if _local_medications:
        return list(_local_medications.values())

    client = get_admin_client()
    if client is None:
        return []

    try:
        result = client.table("medications").select("*").execute()
        return result.data
    except Exception as exc:
        logger.warning("Supabase medications list failed: %s", exc)
        return []


def save_clinical_report(
    evaluation_id: str,
    patient_id: str,
    content: str,
    clinician_id: str | None = None,
) -> str | None:
    """Save a clinical report to the database."""
    report_id = str(uuid.uuid4())
    record = {
        "id": report_id,
        "evaluation_id": evaluation_id,
        "patient_id": patient_id,
        "clinician_id": clinician_id,
        "content": content,
        "status": "final",
    }

    if evaluation_id in _local_evaluations:
        _local_reports[report_id] = record
        return report_id

    client = get_admin_client()
    if client is None:
        return None

    try:
        client.table("clinical_reports").insert(record).execute()
        return report_id
    except Exception as exc:
        logger.warning("Supabase clinical report save failed: %s", exc)
        return None


def get_clinical_reports_by_patient(patient_id: str) -> list[dict[str, Any]]:
    """Get all clinical reports for a patient."""
    if _local_reports:
        return [r for r in _local_reports.values() if r["patient_id"] == patient_id]

    client = get_admin_client()
    if client is None:
        return []

    try:
        result = (
            client.table("clinical_reports")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.warning("Supabase clinical reports lookup failed: %s", exc)
        return []


_local_medications = {}
_local_reports = {}


def is_configured() -> bool:
    return _client is not None


def get_supabase_client() -> Client | None:
    return _client


def get_admin_client() -> Client | None:
    """Returns a client with service_role privileges for auth/admin tasks."""
    return _admin_client


def _row_to_patient(row: dict[str, Any]) -> PatientRecord:
    # Use PatientOut to handle decryption, then convert back to dict for the legacy PatientRecord typing
    p_out = PatientOut.from_db(row)
    return {
        "id": p_out.id,
        "display_name": p_out.display_name,
        "age": p_out.age,
        "sex": p_out.sex,
        "indication": p_out.indication,
        "cyp_profiles": [p.model_dump() for p in p_out.cyp_profiles],
    }


def get_patient_by_id(patient_id: str) -> PatientRecord | None:
    pid = patient_id.upper()
    client = get_admin_client()
    if client is not None:
        try:
            result = (
                client.table("patients")
                .select("*")
                .eq("id", pid)
                .maybe_single()
                .execute()
            )
            if result.data:
                return _row_to_patient(result.data)
        except Exception as exc:
            logger.warning("Supabase patient lookup failed for %s: %s", pid, exc)
    return get_patient(pid)


def list_all_patients() -> list[PatientRecord]:
    client = get_admin_client()
    if client is not None:
        try:
            result = client.table("patients").select("*").order("id").execute()
            if result.data:
                return [_row_to_patient(row) for row in result.data]
        except Exception as exc:
            logger.warning("Supabase patient listing failed: %s", exc)
    return list(PATIENTS.values())


def upsert_patient(patient: PatientRecord) -> PatientRecord:
    client = get_admin_client()
    if client is not None:
        try:
            # Use PatientIn to automatically encrypt sensitive fields
            p_in = PatientIn(**patient)
            data_to_save = p_in.model_dump(
                exclude={"display_name"}
            )  # Don't save plain text
            data_to_save["id"] = data_to_save["id"].upper()

            client.table("patients").upsert(data_to_save).execute()
        except Exception as exc:
            logger.warning(
                "Supabase patient upsert failed for %s: %s", patient["id"], exc
            )
    else:
        PATIENTS[patient["id"].upper()] = patient
    return patient


def save_evaluation(
    patient_id: str,
    medication: str,
    flagged: bool,
    risk_level: str,
    result_json: dict[str, Any],
) -> str:
    evaluation_id = str(result_json.get("evaluation_id") or uuid.uuid4())
    payload = {
        "id": evaluation_id,
        "patient_id": patient_id.upper(),
        "medication": medication,
        "flagged": flagged,
        "risk_level": risk_level,
        "result_json": result_json,
    }

    client = get_admin_client()
    if client is None:
        _local_evaluations[evaluation_id] = {
            **payload,
            "created_at": datetime.now(UTC).isoformat(),
            "review_state": result_json.get("human_gate", {}).get("status", "pending"),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_rationale": None,
        }
        return evaluation_id

    try:
        result = client.table("evaluations").insert(payload).execute()
        if result.data:
            inserted = result.data[0]
            return str(inserted.get("id") or evaluation_id)
    except Exception as exc:
        logger.warning("Supabase evaluation save failed for %s: %s", patient_id, exc)
    _local_evaluations[evaluation_id] = {
        **payload,
        "created_at": datetime.now(UTC).isoformat(),
        "review_state": result_json.get("human_gate", {}).get("status", "pending"),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_rationale": None,
    }
    return evaluation_id


def list_evaluations(patient_id: str, limit: int = 5) -> list[dict]:
    client = get_admin_client()
    if client is None:
        rows = [
            row
            for row in _local_evaluations.values()
            if row["patient_id"] == patient_id.upper()
        ]
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return rows[:limit]
    try:
        result = (
            client.table("evaluations")
            .select("*")
            .eq("patient_id", patient_id.upper())
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.warning("Supabase evaluation list failed: %s", exc)
        return []


def get_evaluation_by_id(evaluation_id: str) -> dict[str, Any] | None:
    """Look up an evaluation, checking the database first if available."""
    client = get_admin_client()
    if client is not None:
        try:
            result = (
                client.table("evaluations")
                .select("*")
                .eq("id", evaluation_id)
                .maybe_single()
                .execute()
            )
            if result.data:
                return result.data
        except Exception as exc:
            logger.warning(
                "Supabase evaluation lookup failed for %s: %s", evaluation_id, exc
            )

    # Fallback to local cache
    return _local_evaluations.get(evaluation_id)


def update_evaluation_decision(
    evaluation_id: str,
    decision: str,
    reviewer: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any] | None:
    normalized = decision.lower().strip()
    if normalized not in {"approved", "rejected"}:
        raise ValueError("decision must be 'approved' or 'rejected'")

    reviewed_at = datetime.now(UTC).isoformat()
    existing = get_evaluation_by_id(evaluation_id)
    if existing is None:
        logger.warning(f"No existing evaluation found for ID: {evaluation_id}")
        return None

    # Deep update of the result_json
    result_json = dict(existing.get("result_json") or {})
    human_gate = dict(result_json.get("human_gate") or {})
    human_gate.update(
        {
            "status": normalized,
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
            "review_notes": rationale,
        }
    )
    result_json["human_gate"] = human_gate

    # Sync local cache regardless of path
    updated_record = {
        **existing,
        "result_json": result_json,
        "review_state": normalized,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "review_rationale": rationale,
    }
    if evaluation_id in _local_evaluations:
        _local_evaluations[evaluation_id].update(updated_record)

    client = get_admin_client()
    if client is None:
        return _local_evaluations.get(evaluation_id)

    try:
        # Update database
        db_res = (
            client.table("evaluations")
            .update({"result_json": result_json})
            .eq("id", evaluation_id)
            .execute()
        )
        if db_res.data:
            logger.info(
                f"Database successfully updated for evaluation: {evaluation_id}"
            )
            return db_res.data[0]
        return updated_record
    except Exception as exc:
        logger.error(
            "Supabase evaluation decision update failed for %s: %s", evaluation_id, exc
        )
        if evaluation_id in _local_evaluations:
            return _local_evaluations[evaluation_id]
        return updated_record


def update_therapy_decision(
    therapy_request_id: str,
    decision: str,
    reviewer: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any] | None:
    """Update the human review status for a therapy generation simulation."""
    normalized = decision.lower().strip()
    if normalized not in {"approved", "rejected"}:
        raise ValueError("decision must be 'approved' or 'rejected'")

    reviewed_at = datetime.now(UTC).isoformat()
    existing = get_therapy_request_by_id(therapy_request_id)
    if existing is None:
        return None

    result_json = dict(existing.get("result_json") or {})
    human_gate = dict(result_json.get("human_gate") or {})
    human_gate.update(
        {
            "status": normalized,
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
            "review_notes": rationale,
        }
    )
    result_json["human_gate"] = human_gate
    updated_record = {
        **existing,
        "result_json": result_json,
        "human_review": {
            **dict(existing.get("human_review") or {}),
            "status": normalized,
            "reviewer_id": reviewer,
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
            "review_notes": rationale,
        },
    }

    if therapy_request_id in _local_therapy_requests:
        _local_therapy_requests[therapy_request_id].update(updated_record)
        return _local_therapy_requests[therapy_request_id]

    client = get_admin_client()
    if client is None:
        return None

    try:
        # Update both the table and the result_json for consistency
        client.table("therapy_requests").update({"result_json": result_json}).eq(
            "id", therapy_request_id
        ).execute()

        result = (
            client.table("therapy_human_reviews")
            .update(
                {
                    "status": normalized,
                    "reviewer_id": reviewer,
                    "reviewed_at": reviewed_at,
                    "review_notes": rationale,
                }
            )
            .eq("therapy_request_id", therapy_request_id)
            .execute()
        )
        return updated_record if result.data is not None else updated_record
    except Exception as exc:
        logger.warning(
            "Supabase therapy decision update failed for %s: %s",
            therapy_request_id,
            exc,
        )
        return updated_record


def list_check_ins_for_patient(patient_id: str, limit: int = 5) -> list[dict]:
    """Fetches recent check-ins for a patient across all their adherence plans. Fixed Bug #7 (N+1 Pattern)."""
    client = get_admin_client()
    if client is None:
        return []
    try:
        # Fixed: Using a single query with join to avoid N+1 pattern
        result = (
            client.table("check_ins")
            .select("*, adherence_plans!inner(medication, patient_id)")
            .eq("adherence_plans.patient_id", patient_id.upper())
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.warning("Supabase check-in list failed: %s", exc)
        return []


def create_adherence_plan(
    patient_id: str, medication: str, evaluation_id: str | None = None
) -> dict[str, Any] | None:
    client = get_admin_client()
    if client is None:
        return _local_adherence_plan(patient_id, medication)
    try:
        result = (
            client.table("adherence_plans")
            .insert(
                {
                    "patient_id": patient_id.upper(),
                    "medication": medication,
                    "evaluation_id": evaluation_id,
                    "status": "active",
                }
            )
            .execute()
        )
        if result.data:
            plan = result.data[0]
            _seed_check_ins(plan["id"], medication)
            full = get_adherence_plan(plan["id"])
            return full or plan
    except Exception as exc:
        logger.warning(
            "Supabase adherence plan creation failed for %s: %s", patient_id, exc
        )
    return _local_adherence_plan(patient_id, medication)


_local_plans: dict[str, dict[str, Any]] = {}
_local_check_ins: dict[str, list[dict[str, Any]]] = {}


def _local_adherence_plan(patient_id: str, medication: str) -> dict[str, Any]:
    import uuid

    plan_id = str(uuid.uuid4())
    plan = {
        "id": plan_id,
        "patient_id": patient_id.upper(),
        "medication": medication,
        "status": "active",
    }
    _local_plans[plan_id] = plan
    _local_check_ins[plan_id] = _default_check_ins(plan_id, medication)
    return plan


def _default_check_ins(plan_id: str, medication: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{plan_id}-d3",
            "plan_id": plan_id,
            "day_offset": 3,
            "prompt": f"Day 3: Are you taking {medication} as prescribed? Any side effects?",
            "status": "pending",
            "response": None,
            "side_effect_reported": False,
        },
        {
            "id": f"{plan_id}-d7",
            "plan_id": plan_id,
            "day_offset": 7,
            "prompt": f"Day 7: How is your pain level? Still on {medication}?",
            "status": "pending",
            "response": None,
            "side_effect_reported": False,
        },
    ]


def _seed_check_ins(plan_id: str, medication: str) -> None:
    client = get_admin_client()
    if client is None:
        return
    for entry in _default_check_ins(plan_id, medication):
        try:
            client.table("check_ins").insert(
                {
                    "plan_id": plan_id,
                    "day_offset": entry["day_offset"],
                    "prompt": entry["prompt"],
                    "status": entry["status"],
                }
            ).execute()
        except Exception as exc:
            logger.warning(
                "Supabase check-in seed failed for plan %s: %s", plan_id, exc
            )


def get_adherence_plan(plan_id: str) -> dict[str, Any] | None:
    if plan_id in _local_plans:
        plan = _local_plans[plan_id]
        return {**plan, "check_ins": _local_check_ins.get(plan_id, [])}
    client = get_admin_client()
    if client is None:
        return None
    try:
        plan_result = (
            client.table("adherence_plans")
            .select("*")
            .eq("id", plan_id)
            .maybe_single()
            .execute()
        )
        if not plan_result.data:
            return None
        check_ins = (
            client.table("check_ins")
            .select("*")
            .eq("plan_id", plan_id)
            .order("day_offset")
            .execute()
        )
        return {**plan_result.data, "check_ins": check_ins.data or []}
    except Exception as exc:
        logger.warning("Supabase adherence plan lookup failed for %s: %s", plan_id, exc)
        return None


def submit_check_in(
    check_in_id: str, response: str, side_effect_reported: bool
) -> dict[str, Any] | None:
    for _plan_id, check_ins in _local_check_ins.items():
        for ci in check_ins:
            if ci["id"] == check_in_id:
                ci["response"] = response
                ci["side_effect_reported"] = side_effect_reported
                ci["status"] = "completed"
                return ci
    client = get_admin_client()
    if client is None:
        return None
    try:
        result = (
            client.table("check_ins")
            .update(
                {
                    "response": response,
                    "side_effect_reported": side_effect_reported,
                    "status": "completed",
                }
            )
            .eq("id", check_in_id)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.warning("Supabase check-in update failed for %s: %s", check_in_id, exc)
        return None


def save_therapy_generation(result_json: dict[str, Any]) -> str:
    """Persist a complete n-of-1 research simulation packet."""
    therapy_request_id = str(result_json.get("therapy_request_id") or uuid.uuid4())
    patient_id = str(result_json.get("patient_id") or "").upper()
    target_disease = str(result_json.get("target_disease") or "")
    created_at = datetime.now(UTC).isoformat()
    request_payload = {
        "id": therapy_request_id,
        "patient_id": patient_id,
        "target_disease": target_disease,
        "status": result_json.get("status", "unknown"),
        "iterations": result_json.get("iterations", 0),
        "result_json": result_json,
    }
    candidates = result_json.get("candidate_history") or []
    validation = result_json.get("validation_result")
    audit_events = result_json.get("audit_trail") or []
    human_gate = result_json.get("human_gate") or {}

    client = get_admin_client()
    if client is None:
        _save_therapy_generation_local(
            therapy_request_id,
            request_payload,
            candidates,
            validation,
            audit_events,
            human_gate,
            created_at,
        )
        return therapy_request_id

    try:
        client.table("therapy_requests").insert(request_payload).execute()
        for candidate in candidates:
            candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())
            client.table("therapy_candidates").insert(
                {
                    "candidate_id": candidate_id,
                    "therapy_request_id": therapy_request_id,
                    "iteration": candidate.get("iteration", 0),
                    "modality": candidate.get("modality", "simulated_mrna"),
                    "sequence": candidate.get("sequence", ""),
                    "design_constraints": candidate.get("design_constraints", []),
                    "rationale": candidate.get("rationale", ""),
                    "evidence_refs": candidate.get("evidence_refs", []),
                }
            ).execute()

        final_candidate = result_json.get("final_candidate") or {}
        candidate_id = final_candidate.get("candidate_id")
        if validation and candidate_id:
            client.table("therapy_validation_results").insert(
                {
                    "therapy_request_id": therapy_request_id,
                    "candidate_id": candidate_id,
                    "passed": validation.get("passed", False),
                    "overall_risk_score": validation.get("overall_risk_score", 1),
                    "checks": validation.get("checks", []),
                    "blocked_reasons": validation.get("blocked_reasons", []),
                    "revision_hints": validation.get("revision_hints", []),
                }
            ).execute()

        for index, event in enumerate(audit_events):
            client.table("therapy_audit_events").insert(
                {
                    "therapy_request_id": therapy_request_id,
                    "event_index": index,
                    "stage": event.get("stage", "unknown"),
                    "decision": event.get("decision", "unknown"),
                    "rationale": event.get("rationale", ""),
                    "requires_human_review": event.get("requires_human_review", True),
                }
            ).execute()

        client.table("therapy_human_reviews").insert(
            {
                "therapy_request_id": therapy_request_id,
                "status": human_gate.get("status", "pending"),
                "reason": human_gate.get("reason", "Human review required."),
                "required_fields": human_gate.get("required_fields", []),
            }
        ).execute()
    except Exception as exc:
        logger.warning(
            "Supabase therapy generation save failed for %s: %s",
            therapy_request_id,
            exc,
        )
        _save_therapy_generation_local(
            therapy_request_id,
            request_payload,
            candidates,
            validation,
            audit_events,
            human_gate,
            created_at,
        )

    return therapy_request_id


def _save_therapy_generation_local(
    therapy_request_id: str,
    request_payload: dict[str, Any],
    candidates: list[dict[str, Any]],
    validation: dict[str, Any] | None,
    audit_events: list[dict[str, Any]],
    human_gate: dict[str, Any],
    created_at: str,
) -> None:
    _local_therapy_requests[therapy_request_id] = {
        **request_payload,
        "created_at": created_at,
        "human_review": {
            "status": human_gate.get("status", "pending"),
            "reason": human_gate.get("reason", "Human review required."),
            "required_fields": human_gate.get("required_fields", []),
        },
    }
    _local_therapy_candidates[therapy_request_id] = candidates
    if validation is not None:
        _local_therapy_validation_results[therapy_request_id] = validation
    _local_therapy_audit_events[therapy_request_id] = audit_events


def get_therapy_request_by_id(therapy_request_id: str) -> dict[str, Any] | None:
    """Return a saved therapy request packet for tests and future API expansion."""
    if therapy_request_id in _local_therapy_requests:
        return {
            **_local_therapy_requests[therapy_request_id],
            "candidate_history": _local_therapy_candidates.get(therapy_request_id, []),
            "validation_result": _local_therapy_validation_results.get(
                therapy_request_id
            ),
            "audit_trail": _local_therapy_audit_events.get(therapy_request_id, []),
        }

    client = get_admin_client()
    if client is None:
        return None

    try:
        result = (
            client.table("therapy_requests")
            .select("*")
            .eq("id", therapy_request_id)
            .maybe_single()
            .execute()
        )
        return result.data or None
    except Exception as exc:
        logger.warning(
            "Supabase therapy request lookup failed for %s: %s",
            therapy_request_id,
            exc,
        )
        return None
