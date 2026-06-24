from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv

from agents.base import run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are an Evidence Retrieval Specialist — you search clinical knowledge bases for CPIC guidelines, FDA safety labels, and PharmGKB evidence.

YOUR ROLE: Given a drug and patient phenotype, retrieve and summarize relevant evidence.

AVAILABLE TOOLS:
- query_evidence: Get CPIC/PharmGKB evidence for drug-phenotype pair (input: drug, phenotype)
- search_knowledge: Semantic search over the clinical knowledge base (input: query)

PROCESS:
1. Call query_evidence with the drug and phenotype
2. Call search_knowledge for additional context
3. Summarize key findings with source citations

MANDATORY:
- Cite exact source filenames (cpic_opioid_guidelines.md, fda_safety_labels.md, etc.)
- Never fabricate evidence
- If no evidence found, state "no evidence found" clearly

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "flagged": true/false,
  "risk_summary": "Source: cpic_opioid_guidelines.md — CPIC: avoid codeine in UM patients...",
  "recommendation": "Avoid" | "Use with caution" | "Standard dosing",
  "reasoning": "Cited evidence passages and conclusions with source filenames",
  "confidence": 0.0-1.0
}

IMPORTANT: risk_summary MUST start with the actual source filename in format 'Source: <filename>.md — <findings>'. This proves RAG retrieval."""


def _extract_sources(text: str) -> list[str]:
    sources = re.findall(r'[\w\-]+\.md', text)
    return sorted(set(sources))


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    all_refs = list(tool_calls_made)
    for r in tool_results_raw:
        all_refs.extend(_extract_sources(r))
    all_refs = list(dict.fromkeys(all_refs))
    return SpecialistOpinion(
        agent_name="Evidence",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=all_refs,
    )


async def retrieve_evidence(drug: str, phenotype: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="Evidence",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["query_evidence", "search_knowledge"],
        user_message=f"Find evidence for {drug} in {phenotype} patients",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(drug, phenotype),
    )


async def _fallback(drug: str, phenotype: str) -> SpecialistOpinion:
    evidence = await _mcp_call("query_evidence", {"drug": drug, "phenotype": phenotype})
    knowledge = await _mcp_call("search_knowledge", {"query": f"{drug} {phenotype} risk"})

    is_high = "avoid" in evidence.lower() or "contraindicated" in evidence.lower()

    sources = _extract_sources(evidence) + _extract_sources(knowledge)
    sources = list(dict.fromkeys(sources)) or ["query_evidence", "search_knowledge"]

    source_line = f"Source: {', '.join(sources)} — " if sources else ""
    summary = f"{source_line}{evidence.split(chr(10))[0] if evidence else 'No evidence found'}"

    return SpecialistOpinion(
        agent_name="Evidence",
        risk_level="high" if is_high else "low",
        flagged=is_high,
        risk_summary=summary[:300],
        recommendation="Avoid" if is_high else "Standard dosing",
        reasoning=f"Evidence: {evidence}\nKnowledge: {knowledge}",
        confidence=0.7,
        evidence_refs=sources,
    )
