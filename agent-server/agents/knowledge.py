from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from config import GROQ_MODEL
from db.vector_store import query_clinical_knowledge

try:
    from groq import Groq

    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

SIMILARITY_THRESHOLD = 0.3


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
    start = time.perf_counter()

    # Step 1: Try semantic retrieval (Phase 1 RAG)
    query = f"{medication} {phenotype} {risk_level} CYP2D6 opioid prodrug"
    semantic_hits = query_clinical_knowledge(query, top_k=5, min_similarity=SIMILARITY_THRESHOLD)

    if semantic_hits:
        sources = sorted({h["source"] for h in semantic_hits})
        context = "\n\n".join(
            f"--- SOURCE: {h['source']} (score: {h['similarity']}) ---\n{h['text']}"
            for h in semantic_hits
        )
        reasoning = (
            f"Retrieved {len(semantic_hits)} semantically relevant chunks "
            f"for {medication} + {phenotype} (threshold={SIMILARITY_THRESHOLD})."
        )

        if _groq is not None and os.environ.get("GROQ_API_KEY"):
            try:
                completion = _groq.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a clinical evidence extraction agent. "
                                "Use only the supplied source text. Return concise "
                                "evidence for a prescribing clinician. "
                                "MANDATORY: Start with the exact source file name "
                                "(e.g., 'Source: cpic_opioid_guidelines.md')."
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
                logger.error("Knowledge LLM extraction failed: %s", e)
                pass

        snippets: list[str] = []
        for h in semantic_hits:
            lines = _extract_relevant_lines(h["text"], medication, phenotype)
            if lines:
                snippets.append(f"{h['source']} (sim={h['similarity']}): {' '.join(lines)}")

        elapsed = int((time.perf_counter() - start) * 1000)
        return "\n".join(snippets) if snippets else context, elapsed, sources

    # Step 2: Fallback to keyword scoring (existing logic)
    logger.info("Semantic retrieval returned no hits, falling back to keyword matching")
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
        reasoning = (
            f"Evaluating if local knowledge for {medication} + {phenotype} is sufficient..."
        )
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
                            "MANDATORY: Start with the exact source file name "
                            "(e.g., 'Source: cpic_opioid_guidelines.md')."
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
            logger.error("Knowledge agent LLM call failed: %s", e)
            pass

    snippets: list[str] = []
    for source, text in relevant:
        lines = _extract_relevant_lines(text, medication, phenotype)
        if lines:
            snippets.append(f"{source}: {' '.join(lines)}")

    elapsed = int((time.perf_counter() - start) * 1000)
    return "\n".join(snippets) if snippets else None, elapsed, sources
