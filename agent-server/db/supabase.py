from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

from models import PatientIn, PatientOut
from pgx.patients import PATIENTS, PatientRecord, get_patient

logger = logging.getLogger(__name__)

try:
    load_dotenv()
    from supabase import Client, create_client

    _url = os.environ.get("SUPABASE_URL")
    _key = os.environ.get("SUPABASE_ANON_KEY")
    _client: Client | None = (
        create_client(_url, _key) if _url and _key else None
    )
except Exception:
    _client = None


def is_configured() -> bool:
    return _client is not None


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
    if _client is not None:
        try:
            result = (
                _client.table("patients")
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
    if _client is not None:
        try:
            result = _client.table("patients").select("*").order("id").execute()
            if result.data:
                return [_row_to_patient(row) for row in result.data]
        except Exception as exc:
            logger.warning("Supabase patient listing failed: %s", exc)
    return list(PATIENTS.values())


def upsert_patient(patient: PatientRecord) -> PatientRecord:
    if _client is not None:
        try:
            # Use PatientIn to automatically encrypt sensitive fields
            p_in = PatientIn(**patient)
            data_to_save = p_in.model_dump(exclude={'display_name'}) # Don't save plain text
            data_to_save['id'] = data_to_save['id'].upper()
            
            _client.table("patients").upsert(data_to_save).execute()
        except Exception as exc:
            logger.warning("Supabase patient upsert failed for %s: %s", patient["id"], exc)
    else:
        PATIENTS[patient["id"].upper()] = patient
    return patient


def save_evaluation(
    patient_id: str,
    medication: str,
    flagged: bool,
    risk_level: str,
    result_json: dict[str, Any],
) -> None:
    if _client is None:
        return
    try:
        _client.table("evaluations").insert(
            {
                "patient_id": patient_id.upper(),
                "medication": medication,
                "flagged": flagged,
                "risk_level": risk_level,
                "result_json": result_json,
            }
        ).execute()
    except Exception as exc:
        logger.warning("Supabase evaluation save failed for %s: %s", patient_id, exc)


def list_evaluations(patient_id: str, limit: int = 5) -> list[dict]:
    if _client is None:
        return []
    try:
        result = (
            _client.table("evaluations")
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


def list_check_ins_for_patient(patient_id: str, limit: int = 5) -> list[dict]:
    """Fetches recent check-ins for a patient across all their adherence plans. Fixed Bug #7 (N+1 Pattern)."""
    if _client is None:
        return []
    try:
        # Fixed: Using a single query with join to avoid N+1 pattern
        result = (
            _client.table("check_ins")
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
    if _client is None:
        return _local_adherence_plan(patient_id, medication)
    try:
        result = (
            _client.table("adherence_plans")
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
        logger.warning("Supabase adherence plan creation failed for %s: %s", patient_id, exc)
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
    if _client is None:
        return
    for entry in _default_check_ins(plan_id, medication):
        try:
            _client.table("check_ins").insert(
                {
                    "plan_id": plan_id,
                    "day_offset": entry["day_offset"],
                    "prompt": entry["prompt"],
                    "status": entry["status"],
                }
            ).execute()
        except Exception as exc:
            logger.warning("Supabase check-in seed failed for plan %s: %s", plan_id, exc)


def get_adherence_plan(plan_id: str) -> dict[str, Any] | None:
    if plan_id in _local_plans:
        plan = _local_plans[plan_id]
        return {**plan, "check_ins": _local_check_ins.get(plan_id, [])}
    if _client is None:
        return None
    try:
        plan_result = (
            _client.table("adherence_plans")
            .select("*")
            .eq("id", plan_id)
            .maybe_single()
            .execute()
        )
        if not plan_result.data:
            return None
        check_ins = (
            _client.table("check_ins")
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
    if _client is None:
        return None
    try:
        result = (
            _client.table("check_ins")
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
