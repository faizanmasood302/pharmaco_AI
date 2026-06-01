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
