from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv

from config import GROQ_MODEL
from models import EvaluationResponse

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


async def generate_clinical_note(evaluation_input: Any) -> str:
    """Generate a structured EHR-ready clinical note from an evaluation."""

    # FORCE conversion to Pydantic model to prevent 'dict' attribute errors
    try:
        if isinstance(evaluation_input, dict):
            evaluation = EvaluationResponse(**evaluation_input)
        else:
            evaluation = evaluation_input
    except Exception as e:
        return f"CRITICAL ERROR: Failed to parse evaluation data. {e}"

    # Enable LLM notes if GROQ_API_KEY is present, unless explicitly disabled
    enable_llm = os.environ.get("ENABLE_LLM_NOTES", "true").lower() == "true"

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
                if profile.gene in risk_summary or any(
                    profile.gene in p for p in evaluation.pathways
                ):
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

        completion = await asyncio.to_thread(
            _groq.chat.completions.create,
            messages=[
                {
                    "role": "system",
                    "content": "You are a Senior Clinical Pharmacogeneticist. Your task is to provide a structured, formal EHR documentation entry.",
                },
                {"role": "user", "content": prompt},
            ],
            model=GROQ_MODEL,
            max_tokens=600,
            temperature=0.2,
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
