"""MCP server: Clinical report generation and management — generate_clinical_note, save_report, list_reports."""

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

from agents.reporter import generate_clinical_note
from db.database import get_clinical_reports_by_patient, save_clinical_report

mcp = FastMCP("clinical-reporter")


@mcp.tool()
def generate_note(evaluation_json: str) -> str:
    """Generate an EHR-ready clinical note from an evaluation JSON string. Uses LLM if available, otherwise deterministic fallback."""
    try:
        data = json.loads(evaluation_json)
        return generate_clinical_note(data)
    except (json.JSONDecodeError, Exception) as e:
        return f"Error: {e}"


@mcp.tool()
def save_report(evaluation_id: str, patient_id: str, content: str, clinician_id: str = "") -> str:
    """Save a clinical report to the database. Returns report_id on success."""
    cid = clinician_id if clinician_id.strip() else None
    report_id = save_clinical_report(evaluation_id, patient_id, content, cid)
    if report_id:
        return json.dumps({"status": "saved", "report_id": report_id})
    return json.dumps({"error": "Failed to save report"})


@mcp.tool()
def list_reports(patient_id: str) -> str:
    """List clinical reports for a patient."""
    return json.dumps(get_clinical_reports_by_patient(patient_id))


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(main())
