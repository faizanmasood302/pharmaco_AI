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
