"""MCP server: PGx deterministic rules engine — assess_prescription, normalize_medication, extract_phenotype, get_cyp2d6/2c19 phenotype."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_agent_server = _this_dir.parent.parent
if str(_agent_server) not in sys.path:
    sys.path.insert(0, str(_agent_server))

from mcp.server.fastmcp import FastMCP

from db.database import get_patient_by_id
from pgx.patients import extract_phenotype
from pgx.rules import assess_prescription, get_cyp2c19_phenotype, get_cyp2d6_phenotype, normalize_medication

mcp = FastMCP("pgx-rules-engine")


@mcp.tool()
def assess_rx(patient_id: str, medication: str) -> str:
    """Run full multi-enzyme deterministic risk assessment for a drug-patient pair. Returns flagged, risk_level, summary, pathways, alternative, rationale, cpic_note, cpic_level."""
    result = assess_prescription(patient_id, medication)
    return json.dumps({
        "flagged": result.flagged,
        "risk_level": result.risk_level,
        "summary": result.risk_summary,
        "pathways": result.pathways,
        "alternative": result.recommended_alternative,
        "rationale": result.alternative_rationale,
        "cpic_note": result.cpic_note,
        "cpic_level": result.cpic_level,
    })


@mcp.tool()
def lookup_drug(medication: str) -> str:
    """Normalize a drug name to the formulary canonical key. Returns {'normalized': str | null, 'found': bool}."""
    result = normalize_medication(medication)
    return json.dumps({"normalized": result, "found": result is not None})


@mcp.tool()
def get_phenotype(patient_data: str) -> str:
    """Extract CYP phenotype from a patient data string (JSON or text). Returns lowercase phenotype string."""
    return extract_phenotype(patient_data)


@mcp.tool()
def get_cyp2d6(patient_id: str) -> str:
    """Get CYP2D6 phenotype for a patient by ID (e.g. PGX-001)."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return json.dumps({"error": f"Patient '{patient_id}' not found"})
    pheno = get_cyp2d6_phenotype(patient)
    return json.dumps({"gene": "CYP2D6", "phenotype": pheno})


@mcp.tool()
def get_cyp2c19(patient_id: str) -> str:
    """Get CYP2C19 phenotype for a patient by ID (e.g. PGX-001)."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return json.dumps({"error": f"Patient '{patient_id}' not found"})
    pheno = get_cyp2c19_phenotype(patient)
    return json.dumps({"gene": "CYP2C19", "phenotype": pheno})


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(main())
