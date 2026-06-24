"""MCP server: FHIR bundle parsing — parse_fhir_bundle."""

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

from fhir.parser import parse_fhir_bundle

mcp = FastMCP("fhir-service")


@mcp.tool()
def parse_bundle(bundle: str) -> str:
    """Parse a FHIR R4 Bundle JSON string into a structured patient record (id, display_name, age, sex, indication, cyp_profiles, current_medications)."""
    try:
        data = json.loads(bundle)
        result = parse_fhir_bundle(data)
        return json.dumps(result)
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": str(e)})


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(main())
