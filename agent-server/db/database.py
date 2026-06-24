from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from models import PatientIn, PatientOut
from pgx.patients import PATIENTS, PatientRecord, get_patient

logger = logging.getLogger(__name__)
load_dotenv()
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()

_local_evaluations: dict[str, dict[str, Any]] = {}
_local_reports: dict[str, dict[str, Any]] = {}
_local_medications: dict[str, dict[str, Any]] = {}
_local_plans: dict[str, dict[str, Any]] = {}
_local_check_ins: dict[str, list[dict[str, Any]]] = {}
_local_therapy_requests: dict[str, dict[str, Any]] = {}
_local_therapy_candidates: dict[str, list[dict[str, Any]]] = {}
_local_therapy_validation_results: dict[str, dict[str, Any]] = {}
_local_therapy_audit_events: dict[str, list[dict[str, Any]]] = {}


_HAS_WARMED_UP = False


def get_connection():
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
        conn.autocommit = True
        return conn
    except Exception as exc:
        logger.warning("Failed to connect to database: %s", exc)
        return None


def warmup_database() -> bool:
    """Ping the database on startup to avoid cold-start delays on first real query."""
    global _HAS_WARMED_UP
    if _HAS_WARMED_UP:
        return True
    conn = get_connection()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        _HAS_WARMED_UP = True
        logger.info("Database connection warmed up successfully")
        return True
    except Exception as exc:
        logger.warning("Database warm-up failed: %s", exc)
        return False
    finally:
        conn.close()


def fetchone(query: str, params: tuple = ()) -> dict[str, Any] | None:
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.error("Database query failed: %s", exc)
        return None
    finally:
        conn.close()


def fetchall(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("Database query failed: %s", exc)
        return []
    finally:
        conn.close()


def execute(query: str, params: tuple = ()) -> int:
    conn = get_connection()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount
    except Exception as exc:
        logger.error("Database execute failed: %s", exc)
        return 0
    finally:
        conn.close()


def insert_one(query: str, params: tuple = ()) -> dict[str, Any] | None:
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.error("Database insert failed: %s", exc)
        return None
    finally:
        conn.close()


def is_configured() -> bool:
    return bool(DATABASE_URL)


def list_medications() -> list[dict[str, Any]]:
    if _local_medications:
        return list(_local_medications.values())
    rows = fetchall("SELECT * FROM medications ORDER BY name")
    if rows:
        return rows
    return []


def _row_to_patient(row: dict[str, Any]) -> PatientRecord:
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
    # Check in-memory cache first to avoid NeonDB cold-start timeout on seed data
    cached = get_patient(pid)
    if cached:
        return cached
    row = fetchone("SELECT * FROM patients WHERE id = %s", (pid,))
    if row:
        return _row_to_patient(row)
    return None


def list_all_patients() -> list[PatientRecord]:
    rows = fetchall("SELECT * FROM patients ORDER BY id")
    if rows:
        return [_row_to_patient(row) for row in rows]
    return list(PATIENTS.values())


def upsert_patient(patient: PatientRecord) -> PatientRecord:
    p_in = PatientIn(**patient)
    # Use mode="json" to guarantee all values (including nested CypProfileOut)
    # are serialized to JSON-safe plain Python types that psycopg2 can adapt.
    data_to_save = p_in.model_dump(mode="json", exclude={"display_name"})
    data_to_save["id"] = data_to_save["id"].upper()
    # Explicitly serialize cyp_profiles to avoid any psycopg2 adapter issues
    data_to_save["cyp_profiles"] = json.dumps(data_to_save["cyp_profiles"])

    conn = get_connection()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO patients (id, display_name_encrypted, age, sex, indication, cyp_profiles)
                       VALUES (%(id)s, %(display_name_encrypted)s, %(age)s, %(sex)s, %(indication)s, %(cyp_profiles)s::jsonb)
                       ON CONFLICT (id) DO UPDATE SET
                         display_name_encrypted = EXCLUDED.display_name_encrypted,
                         age = EXCLUDED.age,
                         sex = EXCLUDED.sex,
                         indication = EXCLUDED.indication,
                         cyp_profiles = EXCLUDED.cyp_profiles,
                         updated_at = NOW()""",
                    data_to_save,
                )
        except Exception as exc:
            logger.warning("Database patient upsert failed for %s: %s", patient["id"], exc)
        finally:
            conn.close()
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
    now = datetime.now(UTC)
    conn = get_connection()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO evaluations (id, patient_id, medication, flagged, risk_level, result_json, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                       RETURNING id""",
                    (
                        evaluation_id,
                        patient_id.upper(),
                        medication,
                        flagged,
                        risk_level,
                        json.dumps(result_json),
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
                if row:
                    logger.info("Evaluation saved to database: %s", evaluation_id)
                    return str(row[0])
        except Exception as exc:
            logger.warning("Database save_evaluation failed: %s", exc)
        finally:
            conn.close()
    _local_evaluations[evaluation_id] = {
        "id": evaluation_id,
        "patient_id": patient_id.upper(),
        "medication": medication,
        "flagged": flagged,
        "risk_level": risk_level,
        "result_json": result_json,
        "created_at": now.isoformat(),
        "review_state": result_json.get("human_gate", {}).get("status", "pending"),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_rationale": None,
    }
    return evaluation_id


def list_evaluations(patient_id: str, limit: int = 5) -> list[dict]:
    rows = [
        row
        for row in _local_evaluations.values()
        if row["patient_id"] == patient_id.upper()
    ]
    if rows:
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return rows[:limit]
    return fetchall(
        "SELECT * FROM evaluations WHERE patient_id = %s ORDER BY created_at DESC LIMIT %s",
        (patient_id.upper(), limit),
    )


def get_evaluation_by_id(evaluation_id: str) -> dict[str, Any] | None:
    row = fetchone("SELECT * FROM evaluations WHERE id = %s", (evaluation_id,))
    if row:
        return row
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
        logger.warning("No existing evaluation found for ID: %s", evaluation_id)
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
        "review_state": normalized,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "review_rationale": rationale,
    }

    if evaluation_id in _local_evaluations:
        _local_evaluations[evaluation_id].update(updated_record)

    execute(
        "UPDATE evaluations SET result_json = %s::jsonb WHERE id = %s",
        (json.dumps(result_json), evaluation_id),
    )
    return _local_evaluations.get(evaluation_id) or updated_record


def save_clinical_report(
    evaluation_id: str,
    patient_id: str,
    content: str,
    clinician_id: str | None = None,
) -> str | None:
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    if evaluation_id in _local_evaluations:
        _local_reports[report_id] = {
            "id": report_id,
            "evaluation_id": evaluation_id,
            "patient_id": patient_id,
            "clinician_id": clinician_id,
            "content": content,
            "status": "final",
        }
        return report_id

    row = insert_one(
        """INSERT INTO clinical_reports (id, evaluation_id, patient_id, clinician_id, content, status, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, 'final', %s, %s)
           RETURNING id""",
        (report_id, evaluation_id, patient_id, clinician_id, content, now, now),
    )
    if row:
        return str(row["id"])
    return None


def get_clinical_reports_by_patient(patient_id: str) -> list[dict[str, Any]]:
    local = [r for r in _local_reports.values() if r["patient_id"] == patient_id]
    if local:
        return local
    return fetchall(
        "SELECT * FROM clinical_reports WHERE patient_id = %s ORDER BY created_at DESC",
        (patient_id,),
    )


def list_check_ins_for_patient(patient_id: str, limit: int = 5) -> list[dict]:
    rows = fetchall(
        """SELECT ci.*
           FROM check_ins ci
           JOIN adherence_plans ap ON ci.plan_id = ap.id
           WHERE ap.patient_id = %s AND ci.status = 'completed'
           ORDER BY ci.created_at DESC
           LIMIT %s""",
        (patient_id.upper(), limit),
    )
    return rows


def create_adherence_plan(
    patient_id: str, medication: str, evaluation_id: str | None = None
) -> dict[str, Any] | None:
    conn = get_connection()
    if conn is not None:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO adherence_plans (patient_id, medication, evaluation_id, status)
                       VALUES (%s, %s, %s, 'active')
                       RETURNING *""",
                    (patient_id.upper(), medication, evaluation_id),
                )
                plan = dict(cur.fetchone())
                # Seed check-ins
                for entry in _default_check_ins(plan["id"], medication):
                    cur.execute(
                        """INSERT INTO check_ins (plan_id, day_offset, prompt, status)
                           VALUES (%s, %s, %s, %s)""",
                        (plan["id"], entry["day_offset"], entry["prompt"], entry["status"]),
                    )
                full = get_adherence_plan(plan["id"])
                return full or plan
        except Exception as exc:
            logger.warning("Database create_adherence_plan failed: %s", exc)
        finally:
            conn.close()
    return _local_adherence_plan(patient_id, medication)


def _local_adherence_plan(patient_id: str, medication: str) -> dict[str, Any]:
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


def get_adherence_plan(plan_id: str) -> dict[str, Any] | None:
    if plan_id in _local_plans:
        plan = _local_plans[plan_id]
        return {**plan, "check_ins": _local_check_ins.get(plan_id, [])}
    plan = fetchone("SELECT * FROM adherence_plans WHERE id = %s", (plan_id,))
    if not plan:
        return None
    check_ins = fetchall(
        "SELECT * FROM check_ins WHERE plan_id = %s ORDER BY day_offset",
        (plan_id,),
    )
    return {**plan, "check_ins": check_ins}


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
    row = insert_one(
        """UPDATE check_ins SET response = %s, side_effect_reported = %s, status = 'completed', updated_at = NOW()
           WHERE id = %s
           RETURNING *""",
        (response, side_effect_reported, check_in_id),
    )
    return row


def save_therapy_generation(result_json: dict[str, Any]) -> str:
    therapy_request_id = str(result_json.get("therapy_request_id") or uuid.uuid4())
    patient_id = str(result_json.get("patient_id") or "").upper()
    target_disease = str(result_json.get("target_disease") or "")
    now = datetime.now(UTC)
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

    conn = get_connection()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO therapy_requests (id, patient_id, target_disease, status, iterations, result_json, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        therapy_request_id,
                        patient_id,
                        target_disease,
                        request_payload["status"],
                        request_payload["iterations"],
                        json.dumps(result_json),
                        now,
                        now,
                    ),
                )

                for candidate in candidates:
                    candidate_id = candidate.get("candidate_id") or str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO therapy_candidates (candidate_id, therapy_request_id, iteration, modality, sequence, design_constraints, rationale, evidence_refs)
                           VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
                           ON CONFLICT (candidate_id) DO NOTHING""",
                        (
                            candidate_id,
                            therapy_request_id,
                            candidate.get("iteration", 0),
                            candidate.get("modality", "simulated_mrna"),
                            candidate.get("sequence", ""),
                            json.dumps(candidate.get("design_constraints", [])),
                            candidate.get("rationale", ""),
                            json.dumps(candidate.get("evidence_refs", [])),
                        ),
                    )

                final_candidate = result_json.get("final_candidate") or {}
                candidate_id = final_candidate.get("candidate_id")
                if validation and candidate_id:
                    cur.execute(
                        """INSERT INTO therapy_validation_results (therapy_request_id, candidate_id, passed, overall_risk_score, checks, blocked_reasons, revision_hints)
                           VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)""",
                        (
                            therapy_request_id,
                            candidate_id,
                            validation.get("passed", False),
                            validation.get("overall_risk_score", 1),
                            json.dumps(validation.get("checks", [])),
                            json.dumps(validation.get("blocked_reasons", [])),
                            json.dumps(validation.get("revision_hints", [])),
                        ),
                    )

                for index, event in enumerate(audit_events):
                    cur.execute(
                        """INSERT INTO therapy_audit_events (therapy_request_id, event_index, stage, decision, rationale, requires_human_review)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (
                            therapy_request_id,
                            index,
                            event.get("stage", "unknown"),
                            event.get("decision", "unknown"),
                            event.get("rationale", ""),
                            event.get("requires_human_review", True),
                        ),
                    )

                cur.execute(
                    """INSERT INTO therapy_human_reviews (therapy_request_id, status, reason, required_fields)
                       VALUES (%s, %s, %s, %s::jsonb)""",
                    (
                        therapy_request_id,
                        human_gate.get("status", "pending"),
                        human_gate.get("reason", "Human review required."),
                        json.dumps(human_gate.get("required_fields", [])),
                    ),
                )
        except Exception as exc:
            logger.warning("Database save_therapy_generation failed for %s: %s", therapy_request_id, exc)
            conn.close()
            conn = None
        finally:
            if conn is not None:
                conn.close()

    # Local fallback if DB unavailable
    _local_therapy_requests[therapy_request_id] = {
        **request_payload,
        "created_at": now.isoformat(),
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

    return therapy_request_id


def get_therapy_request_by_id(therapy_request_id: str) -> dict[str, Any] | None:
    if therapy_request_id in _local_therapy_requests:
        return {
            **_local_therapy_requests[therapy_request_id],
            "candidate_history": _local_therapy_candidates.get(therapy_request_id, []),
            "validation_result": _local_therapy_validation_results.get(therapy_request_id),
            "audit_trail": _local_therapy_audit_events.get(therapy_request_id, []),
        }
    return fetchone(
        "SELECT * FROM therapy_requests WHERE id = %s",
        (therapy_request_id,),
    )


def update_therapy_decision(
    therapy_request_id: str,
    decision: str,
    reviewer: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any] | None:
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

    conn = get_connection()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE therapy_requests SET result_json = %s::jsonb WHERE id = %s",
                    (json.dumps(result_json), therapy_request_id),
                )
                cur.execute(
                    """UPDATE therapy_human_reviews
                       SET status = %s, reviewer_id = %s, reviewed_at = %s, review_notes = %s
                       WHERE therapy_request_id = %s""",
                    (normalized, reviewer, reviewed_at, rationale, therapy_request_id),
                )
        except Exception as exc:
            logger.warning("Database update_therapy_decision failed for %s: %s", therapy_request_id, exc)
        finally:
            conn.close()
    return updated_record
