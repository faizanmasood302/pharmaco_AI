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
