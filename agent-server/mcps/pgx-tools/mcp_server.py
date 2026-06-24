"""MCP server exposing PGx tools via FastMCP (stdio transport)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_agent_server = _this_dir.parent.parent  # mcps/ → agent-server/
if str(_agent_server) not in sys.path:
    sys.path.insert(0, str(_agent_server))

from mcp.server.fastmcp import FastMCP

from agents.tools import (
    _registry,
    _tool_query_alternative_drugs,
    _tool_query_evidence,
    _tool_query_patient,
)

mcp = FastMCP("pgx-tools")

for tool_name in [
    "query_drug_db",
    "lookup_patient_history",
    "search_knowledge",
    "get_phenotype_info",
    "query_clinical_guideline",
    "calculate_egfr",
]:
    t = _registry[tool_name]
    mcp.add_tool(t.fn, name=t.name, description=t.description)

mcp.add_tool(_tool_query_patient, name="query_patient", description="Retrieve patient genetic profile and phenotype data by patient ID.")
mcp.add_tool(_tool_query_evidence, name="query_evidence", description="Query CPIC/PharmGKB clinical evidence for a drug-phenotype pair.")
mcp.add_tool(_tool_query_alternative_drugs, name="query_alternative_drugs", description="Look up formulary alternative drugs for a given drug and phenotype.")


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
