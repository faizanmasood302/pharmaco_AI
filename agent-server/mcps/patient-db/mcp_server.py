"""MCP server: Patient database CRUD — list_patients, list_medications, get_patient, upsert_patient."""

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

from db.database import get_patient_by_id, list_all_patients, list_medications, upsert_patient

mcp = FastMCP("patient-db")


@mcp.tool()
def list_patients() -> str:
    """List all patients in the system."""
    return json.dumps(list_all_patients())


@mcp.tool()
def list_meds() -> str:
    """List all formulary medications."""
    return json.dumps(list_medications())


@mcp.tool()
def get_patient(patient_id: str) -> str:
    """Get a patient by ID (e.g. PGX-001). Returns id, display_name, age, sex, indication, cyp_profiles."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return json.dumps({"error": f"Patient '{patient_id}' not found"})
    return json.dumps(patient)


@mcp.tool()
def upsert(patient_data: str) -> str:
    """Create or update a patient record. Accepts a JSON patient data string."""
    try:
        data = json.loads(patient_data)
        result = upsert_patient(data)
        return json.dumps({"status": "ok", "patient_id": result.get("id")})
    except (json.JSONDecodeError, Exception) as e:
        return json.dumps({"error": str(e)})


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(main())
