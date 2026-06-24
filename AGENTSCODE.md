# Multi-Agent PGx Platform — Source Code

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          External MCP Clients                               │
│  (opencode.json, Claude Desktop, any MCP-compatible client)                │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │  stdio (subprocess)
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         5 MCP Servers (FastMCP, stdio)                     │
│                                                                             │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────┐  ┌───────────┐  ┌──────┐│
│  │  pgx-tools  │  │pgx-rules-engine│  │fhir-svc  │  │patient-db│  │clinical│
│  │   (9 tools) │  │   (5 tools)    │  │ (1 tool) │  │ (4 tools) │  │reporter│
│  └──────┬──────┘  └───────┬────────┘  └────┬─────┘  └─────┬─────┘  │(3 tls)│
│         │                 │               │           │           └────┬──┘
└─────────┼─────────────────┼───────────────┼───────────┼────────────────┼──┘
          │                 │               │           │                │
          ▼                 ▼               ▼           ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Internal Python Runtime (agents/*)                        │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  MCPClient Singleton (mcp_client.py)                                 │   │
│  │  - Spawns all 5 MCP servers as subprocesses at startup               │   │
│  │  - Routes tool calls via tool→server map                             │   │
│  │  - Falls back to agents.tools.execute_tool() on failure              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │               orchestrator_agent.py (async)                          │   │
│  │  evaluate_prescription(patient_id, medication) → EvaluationResponse  │   │
│  │                                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │ RxRisk   │ │ Evidence │ │Adherence │ │ Misuse   │ │CostNav   │   │   │
│  │  │ (Groq    │ │ (Groq    │ │ (Groq    │ │ (Groq    │ │ (Groq    │   │   │
│  │  │ +fallbk) │ │ +fallbk) │ │ +fallbk) │ │ +fallbk) │ │ +fallbk) │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  │                              │    ┌──────────────────────────────┐   │   │
│  │                              │    │ Adjudicator (LLM/deterministic)│   │   │
│  │                              │    │ Synthesizes 5 → final decision│   │   │
│  │                              │    └──────────────────────────────┘   │   │
│  │                              ▼                                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  Human Gate (always required, status="pending")              │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  tools.py — Shared tool registry (query_patient,                    │   │
│  │  query_drug_db, search_knowledge, get_phenotype_info,               │   │
│  │  calculate_egfr, lookup_patient_history, query_evidence, ...)      │   │
│  │          ↕ (both MCP and direct call paths go here)                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  db/vector_store.py — ChromaDB (5 CPIC/FDA/PharmGKB docs)          │   │
│  │  db/database.py — NeonDB (patients, evaluations, sessions)          │   │
│  │  pgx/rules.py — 9 drug rules, 4 patient profiles                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Two-tier MCP architecture:**
- **External clients** (opencode.json, Claude Desktop) → connect to MCP servers directly via stdio
- **Internal agents** → connect through `MCPClient` singleton which spawns the same MCP servers as subprocesses
- **Fallback**: if MCP servers are unreachable (e.g. during tests), agents fall back to direct `agents.tools.execute_tool()` calls

**5 Specialist Agents + 1 Orchestrator + 1 Human Gate = 7-stage pipeline**
**5 MCP Servers = 22 total tools**

---

## Part I: MCP Infrastructure

All MCP servers live under `agent-server/mcps/<name>/mcp_server.py`. They use **FastMCP** from the official `mcp` Python SDK (v1.28.0+) by Anthropic, with stdio transport. Each server is a standalone Python process that the `MCPClient` singleton spawns at app startup.

### Tool-to-Server Mapping

| MCP Server | Tools | Source Module(s) |
|---|---|---|
| **pgx-tools** (9) | query_drug_db, lookup_patient_history, search_knowledge, get_phenotype_info, query_clinical_guideline, calculate_egfr, query_patient, query_evidence, query_alternative_drugs | agents/tools.py |
| **pgx-rules-engine** (5) | assess_rx, lookup_drug, get_phenotype, get_cyp2d6, get_cyp2c19 | pgx/rules.py, pgx/patients.py, db/database.py |
| **fhir-service** (1) | parse_bundle | fhir/parser.py |
| **patient-db** (4) | list_patients, list_meds, get_patient, upsert | db/database.py |
| **clinical-reporter** (3) | generate_note, save_report, list_reports | agents/reporter.py, db/database.py |

### Connection Flow

```
Agent ._fallback()
     │
     ▼
mcp_client.call_tool(name, args)   ← module-level function with auto-fallback
     │
     ├─ MCPClient.call_tool(name, args)  → finds server via _tool_map → _ServerConnection.call_tool()
     │      │                                    │
     │      │                                    ▼ subprocess stdin/stdout JSON-RPC
     │      │                           ┌──────────────────────┐
     │      │                           │ mcp_server.py process│
     │      │                           │  (FastMCP stdio)     │
     │      │                           └──────────────────────┘
     │      │                                    │
     │      │                                    ▼
     │      │                           Direct Python function call
     │
     └─ MCPUnavailableError → agents.tools.execute_tool(name, args)  [direct fallback]
```

---

### MCP 1: mcp_client.py (279 lines)

The central bridge — a singleton that spawns all 5 MCP servers at startup, manages JSON-RPC communication, and provides a fallback-safe `call_tool()` entry point for agents.

```python
"""MCPClient singleton — connects to all local MCP servers via stdio.
Agents call tools through MCP first, with a direct-Python fallback on failure."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent  # agent-server/

SERVER_CONFIG: list[dict[str, Any]] = [
    {"name": "pgx-tools", "path": "mcps/pgx-tools/mcp_server.py"},
    {"name": "pgx-rules-engine", "path": "mcps/pgx-rules-engine/mcp_server.py"},
    {"name": "fhir-service", "path": "mcps/fhir-service/mcp_server.py"},
    {"name": "patient-db", "path": "mcps/patient-db/mcp_server.py"},
    {"name": "clinical-reporter", "path": "mcps/clinical-reporter/mcp_server.py"},
]


class MCPUnavailableError(Exception):
    """Raised when an MCP server is unreachable or returns an error."""


class _ServerConnection:
    """Manages a single MCP server subprocess + JSON-RPC over stdio."""

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = str(BASE / path)
        self._proc: asyncio.subprocess.Process | None = None
        self._tools: list[dict[str, Any]] = []
        self._tool_names: set[str] = set()
        self._read_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._next_id: int = 1
        self._reader_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self) -> None:
        """Spawn subprocess and perform MCP initialize handshake."""
        try:
            self._proc = await asyncio.create_subprocess_exec(
                sys.executable, self.path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise MCPUnavailableError(f"Server {self.name} executable not found")

        self._reader_task = asyncio.create_task(self._read_loop())

        resp = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pgx-mcp-client", "version": "1.0"},
        })
        if not resp:
            raise MCPUnavailableError(f"Server {self.name} initialize failed")

        await self._notify("notifications/initialized")

        # Fetch tools
        tool_result = await self._request("tools/list")
        self._tools = (tool_result or {}).get("tools", [])
        self._tool_names = {t["name"] for t in self._tools}
        self._connected = True
        logger.info("MCP connected: %s (%d tools)", self.name, len(self._tools))

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Call a tool on this server. Returns text content."""
        resp = await self._request("tools/call", {"name": name, "arguments": args})
        if resp is None:
            raise MCPUnavailableError(f"Tool {name} returned no response")
        content = resp.get("content", [])
        if content:
            return content[0].get("text", "")
        return json.dumps(resp)

    @property
    def is_connected(self) -> bool:
        return self._connected and self._proc is not None and self._proc.returncode is None

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible function schemas."""
        out: list[dict[str, Any]] = []
        for t in self._tools:
            out.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {}),
                },
            })
        return out

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except Exception:
                self._proc.kill()
            self._proc = None

    # ---- internal ----

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        msg_id = self._next_id
        self._next_id += 1
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._pending[msg_id] = future

        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params

        try:
            await self._send(payload)
            result = await asyncio.wait_for(future, timeout=15)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise MCPUnavailableError(f"Server {self.name} timed out on {method}")
        finally:
            self._pending.pop(msg_id, None)

    async def _notify(self, method: str) -> None:
        await self._send({"jsonrpc": "2.0", "method": method})

    async def _send(self, msg: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise MCPUnavailableError(f"Server {self.name} not running")
        line = (json.dumps(msg) + "\n").encode()
        try:
            self._proc.stdin.write(line)
            await self._proc.stdin.drain()
        except BrokenPipeError:
            raise MCPUnavailableError(f"Server {self.name} pipe broken")

    async def _read_loop(self) -> None:
        """Continuously read JSON-RPC responses from stdout."""
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            try:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=None)
            except asyncio.CancelledError:
                break
            except Exception:
                break
            if not line:
                break
            try:
                msg = json.loads(line.decode().strip())
            except json.JSONDecodeError:
                continue

            # Route to pending future
            if "id" in msg:
                future = self._pending.pop(msg.get("id"), None)
                if future and not future.done():
                    if "error" in msg:
                        future.set_exception(MCPUnavailableError(str(msg["error"])))
                    else:
                        future.set_result(msg.get("result"))


class MCPClient:
    """Singleton — manages all MCP server connections."""

    _instance: MCPClient | None = None

    def __init__(self) -> None:
        self._servers: dict[str, _ServerConnection] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> server_name
        self._schema_cache: list[dict[str, Any]] = []
        self._connected = False

    @classmethod
    def get_instance(cls) -> MCPClient:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect_all(self) -> None:
        """Start all MCP servers and build the tool map."""
        self._servers = {}
        self._tool_map = {}

        async def _connect_one(cfg: dict[str, Any]) -> _ServerConnection | None:
            conn = _ServerConnection(cfg["name"], cfg["path"])
            try:
                await conn.connect()
                return conn
            except MCPUnavailableError as e:
                logger.warning("MCP server '%s' failed to connect: %s", cfg["name"], e)
                return None
            except Exception as e:
                logger.warning("MCP server '%s' unexpected error: %s", cfg["name"], e)
                return None

        results = await asyncio.gather(*[_connect_one(c) for c in SERVER_CONFIG])

        for cfg, conn in zip(SERVER_CONFIG, results):
            if conn is None:
                continue
            self._servers[cfg["name"]] = conn
            for tool_name in conn._tool_names:
                self._tool_map[tool_name] = cfg["name"]

        self._rebuild_schema_cache()
        self._connected = bool(self._servers)
        logger.info(
            "MCP client: %d/%d servers connected, %d tools mapped",
            len(self._servers), len(SERVER_CONFIG), len(self._tool_map),
        )

    def _rebuild_schema_cache(self) -> None:
        schemas: list[dict[str, Any]] = []
        for conn in self._servers.values():
            schemas.extend(conn.tool_schemas)
        self._schema_cache = schemas

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool schemas from ALL connected MCP servers."""
        if not self._schema_cache:
            from agents.tools import get_tool_schemas as legacy_schemas
            return legacy_schemas()
        return self._schema_cache

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Call a tool via MCP. Falls back to direct Python call on failure."""
        server_name = self._tool_map.get(name)
        if server_name is None:
            raise MCPUnavailableError(f"Tool '{name}' not found in any MCP server")
        conn = self._servers.get(server_name)
        if conn is None or not conn.is_connected:
            raise MCPUnavailableError(f"Server '{server_name}' is not connected")

        try:
            return await conn.call_tool(name, args)
        except (MCPUnavailableError, Exception) as e:
            logger.warning("MCP call_tool(%s) failed, will fallback: %s", name, e)
            raise MCPUnavailableError(str(e))

    async def disconnect_all(self) -> None:
        for conn in self._servers.values():
            await conn.disconnect()
        self._servers = {}
        self._tool_map = {}
        self._schema_cache = []
        self._connected = False
        logger.info("MCP client: all servers disconnected")


async def call_tool(name: str, args: dict[str, Any]) -> str:
    """Try MCP first, fall back to direct Python call.

    This is the public entry point for all agent fallbacks.
    MCP servers may not be running (e.g. during tests), so
    we silently fall back to agents.tools.execute_tool().
    """
    try:
        return await MCPClient.get_instance().call_tool(name, args)
    except MCPUnavailableError:
        from agents.tools import execute_tool as _direct
        return _direct(name, args)
```

---

### MCP 2: pgx-tools Server (mcps/pgx-tools/mcp_server.py, 51 lines)

Exposes 9 PGx tools. 6 are generic tools from the `_registry` (query_drug_db, lookup_patient_history, search_knowledge, get_phenotype_info, query_clinical_guideline, calculate_egfr). 3 are agent-specific wrappers added individually (query_patient, query_evidence, query_alternative_drugs). All delegate to `agents/tools.py` functions.

```python
"""MCP server exposing PGx tools via FastMCP (stdio transport)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_agent_server = _this_dir.parent.parent  # mcps/ -> agent-server/
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
```

---

### MCP 3: pgx-rules-engine Server (mcps/pgx-rules-engine/mcp_server.py, 80 lines)

Exposes 5 tools for deterministic CPIC-guided risk assessment. Uses FastMCP's `@mcp.tool()` decorator pattern. Calls into `pgx/rules.py` and `pgx/patients.py` directly.

```python
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
```

---

### MCP 4: fhir-service Server (mcps/fhir-service/mcp_server.py, 40 lines)

Exposes 1 tool for parsing FHIR R4 bundles into structured patient records.

```python
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
```

---

### MCP 5: patient-db Server (mcps/patient-db/mcp_server.py, 61 lines)

Exposes 4 CRUD tools for the patient database.

```python
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
```

---

### MCP 6: clinical-reporter Server (mcps/clinical-reporter/mcp_server.py, 56 lines)

Exposes 3 tools for generating and managing EHR-ready clinical notes.

```python
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
```

---

### MCP Wiring in opencode.json (opencode.json, 105 lines)

All 5 MCP servers are wired for external clients via `opencode.json`. The same servers are also spawned internally by `MCPClient`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "default_agent": "pgx-orchestrator",
  "agent": {
    "pgx-orchestrator": {
      "description": "Main PGx coordinator — manages 5 specialist subagents: drug-gene risk, evidence, adherence, misuse monitor, cost navigator",
      "mode": "primary",
      "model": "openai/gpt-4o",
      "permission": {
        "read": "allow",
        "glob": "allow",
        "grep": "allow",
        "bash": "allow",
        "edit": "allow"
      }
    },
    "rx-risk": {
      "description": "Subagent: evaluates drug-gene interaction risk using CPIC guidelines",
      "mode": "subagent",
      "model": "openai/gpt-4o-mini",
      "permission": {
        "read": "allow",
        "grep": "allow",
        "glob": "deny",
        "bash": "deny",
        "edit": "deny"
      }
    },
    "adherence-monitor": {
      "description": "Subagent: analyzes patient medication adherence patterns by phenotype",
      "mode": "subagent",
      "model": "openai/gpt-4o-mini",
      "permission": {
        "read": "allow",
        "grep": "allow",
        "glob": "deny",
        "bash": "deny",
        "edit": "deny"
      }
    },
    "evidence-retriever": {
      "description": "Subagent: queries knowledge base for CPIC, FDA, and PharmGKB evidence",
      "mode": "subagent",
      "model": "openai/gpt-4o-mini",
      "permission": {
        "read": "allow",
        "glob": "allow",
        "grep": "allow",
        "bash": "deny",
        "edit": "deny"
      }
    },
    "misuse-monitor": {
      "description": "Subagent: detects prescription misuse risk — refill anomalies, dose escalation, polypharmacy flags",
      "mode": "subagent",
      "model": "openai/gpt-4o-mini",
      "permission": {
        "read": "allow",
        "grep": "allow",
        "glob": "deny",
        "bash": "deny",
        "edit": "deny"
      }
    },
    "cost-navigator": {
      "description": "Subagent: finds affordable therapeutic alternatives based on genetics and formulary data",
      "mode": "subagent",
      "model": "openai/gpt-4o-mini",
      "permission": {
        "read": "allow",
        "grep": "allow",
        "glob": "deny",
        "bash": "deny",
        "edit": "deny"
      }
    }
  },
  "mcp": {
    "pgx-tools": {
      "type": "local",
      "command": ["python", "agent-server/mcps/pgx-tools/mcp_server.py"],
      "cwd": "."
    },
    "pgx-rules-engine": {
      "type": "local",
      "command": ["python", "agent-server/mcps/pgx-rules-engine/mcp_server.py"],
      "cwd": "."
    },
    "fhir-service": {
      "type": "local",
      "command": ["python", "agent-server/mcps/fhir-service/mcp_server.py"],
      "cwd": "."
    },
    "patient-db": {
      "type": "local",
      "command": ["python", "agent-server/mcps/patient-db/mcp_server.py"],
      "cwd": "."
    },
    "clinical-reporter": {
      "type": "local",
      "command": ["python", "agent-server/mcps/clinical-reporter/mcp_server.py"],
      "cwd": "."
    }
  }
}
```

---

## Part II: Base Agent Architecture

### base.py (145 lines)

Shared async driver used by all 5 specialist agents. Manages the Groq LLM loop, tool execution (MCP-first with fallback), consistency checks, and opinion parsing.

```python
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from config import GROQ_MODEL
from models import SpecialistOpinion

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


def log_risk_discrepancy(agent_name: str, patient_id: str, medication: str):
    """Returns a consistency_check callable that logs when LLM and
    deterministic risk levels disagree."""
    async def _check(llm_result: SpecialistOpinion, det_result: SpecialistOpinion) -> None:
        if llm_result.risk_level != det_result.risk_level:
            logger.warning(
                "Consistency: %s risk mismatch for %s/%s — LLM=%s, deterministic=%s",
                agent_name, patient_id, medication,
                llm_result.risk_level, det_result.risk_level,
            )
        if llm_result.flagged != det_result.flagged:
            logger.warning(
                "Consistency: %s flagged mismatch for %s/%s — LLM=%s, deterministic=%s",
                agent_name, patient_id, medication,
                llm_result.flagged, det_result.flagged,
            )
    return _check


def parse_opinion(text: str) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def _execute_tool(name: str, args: dict) -> str:
    from agents.mcp_client import MCPClient, MCPUnavailableError
    try:
        return await MCPClient.get_instance().call_tool(name, args)
    except MCPUnavailableError:
        from agents.tools import execute_tool as legacy_execute
        return legacy_execute(name, args)


async def run_specialist_agent(
    agent_name: str,
    system_prompt: str,
    tools: list[dict[str, Any]],
    user_message: str,
    build_opinion: Callable[[dict, list[str], list[str], str], SpecialistOpinion],
    fallback: Callable[[], Awaitable[SpecialistOpinion]],
    post_process: Callable[[dict], dict] | None = None,
    consistency_check: Callable[[SpecialistOpinion, SpecialistOpinion], Awaitable[None]] | None = None,
) -> SpecialistOpinion:
    start = time.perf_counter()

    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        return await fallback()

    from agents.mcp_client import MCPClient
    tool_schemas = MCPClient.get_instance().get_tool_schemas()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tool_calls_made: list[str] = []
    tool_results_raw: list[str] = []
    for iteration in range(1, 6):
        try:
            response = await asyncio.to_thread(
                _groq.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0.3,
            )
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "stop" and msg.content:
                parsed = parse_opinion(msg.content)
                if post_process:
                    parsed = post_process(parsed)
                result = build_opinion(parsed, tool_calls_made, tool_results_raw, msg.content)
                if consistency_check:
                    det_result = await fallback()
                    await consistency_check(result, det_result)
                return result

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    func = tc.function
                    name = func.name
                    try:
                        args = json.loads(func.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    result = await _execute_tool(name, args)
                    tool_calls_made.append(name)
                    tool_results_raw.append(result)

                    messages.append({
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": name, "arguments": func.arguments},
                        }],
                    })
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            if msg.content:
                messages.append({"role": "assistant", "content": msg.content})
                continue

        except Exception as exc:
            logger.warning("%s agent iteration %d failed: %s", agent_name, iteration, exc)
            return await fallback()

    return await fallback()
```

---

## Part III: Orchestrator

### orchestrator_agent.py (333 lines)

The central entry point — `evaluate_prescription()` calls all 5 specialists in parallel via `asyncio.gather`, adjudicates their opinions (LLM or deterministic), and returns an `EvaluationResponse`. Async throughout.

```python
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid

from dotenv import load_dotenv

from config import GROQ_MODEL
from models import (
    AgentStep,
    AuditEvent,
    EvaluationResponse,
    HumanGate,
    PatientOut,
    CypProfileOut,
    SpecialistOpinion,
)

logger = logging.getLogger(__name__)
load_dotenv()

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None

ADJUDICATOR_PROMPT = """You are the PGx Adjudicator — you synthesize opinions from 5 specialist agents into a final prescribing decision.

SPECIALIST INPUTS:
1. RxRisk: Drug-gene interaction risk assessment
2. Evidence: Clinical evidence from CPIC/FDA/PharmGKB guidelines
3. Adherence: Predicted patient adherence risk based on phenotype
4. MisuseMonitor: Prescription misuse and abuse potential
5. CostNavigator: Cost-effective alternative analysis

YOUR JOB:
- Review all 5 specialist opinions
- Determine consensus risk level
- Decide if the prescription should be blocked
- Recommend an alternative if needed
- Produce a clinical narrative explaining the decision

RULES:
- If ANY specialist flags high risk -> block the prescription
- If ALL specialists agree low risk -> approve
- Always require human gate review
- Cite the specialist opinions that drove the decision

Return JSON:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "agent_verdict": "blocked" | "review_required" | "approved",
  "clinical_narrative": "Concise clinical explanation",
  "recommended_alternative": "Drug name or null",
  "alternative_rationale": "Why this alternative is safer",
  "decision_confidence": 0.0-1.0,
  "safety_notes": ["note1", "note2"]
}"""


async def evaluate_prescription(patient_id: str, medication: str) -> EvaluationResponse:
    start_time = time.perf_counter()
    evaluation_id = str(uuid.uuid4())

    patient_data = _get_patient_data(patient_id)
    patient_out = _build_patient_out(patient_data) if patient_data else None

    opinions = await _run_specialists(patient_id, medication)
    agent_steps = _build_agent_steps(opinions, start_time)

    adjudicated = _adjudicate(opinions, patient_id, medication)

    risk_level = adjudicated.get("risk_level", "low")
    is_flagged = risk_level in ("high", "critical", "moderate")

    safety_notes = [
        "Synthetic demo data only; not for autonomous dispensing.",
        "Clinician approval required before release.",
    ]
    if any(o.confidence < 0.6 for o in opinions):
        safety_notes.append("Low confidence in one or more specialist assessments.")

    response = EvaluationResponse(
        evaluation_id=evaluation_id,
        status="success",
        patient_id=patient_id.upper(),
        medication=medication,
        flagged=is_flagged,
        risk_level=risk_level,
        risk_summary=adjudicated.get("clinical_narrative", "Evaluation complete."),
        pathways=[],
        recommended_alternative=adjudicated.get("recommended_alternative"),
        alternative_rationale=adjudicated.get("alternative_rationale", ""),
        cpic_note="CPIC: see individual specialist evidence.",
        cpic_level="informative",
        patient=patient_out,
        agent_steps=agent_steps,
        clinical_narrative=adjudicated.get("clinical_narrative"),
        clinical_evidence=_build_evidence_summary(opinions),
        evidence_sources=[ref for o in opinions for ref in o.evidence_refs],
        decision_confidence=adjudicated.get("decision_confidence", 0.8),
        safety_notes=safety_notes,
        agent_verdict=adjudicated.get("agent_verdict", "review_required"),
        audit_trail=_build_audit_trail(opinions),
        logic_tree=_build_logic_tree(opinions),
        human_gate=HumanGate(
            required=True,
            status="pending",
            reason="Clinician approval required before release.",
        ),
        next_best_actions=[
            "Review specialist opinions in agent pipeline.",
            "Check patient profile and evidence sources.",
            "Approve or reject via human gate endpoint.",
        ],
    )

    try:
        from db.database import save_evaluation
        persisted = save_evaluation(
            response.patient_id,
            response.medication,
            response.flagged,
            response.risk_level,
            response.model_dump(),
        )
        response.evaluation_id = persisted
    except Exception as exc:
        logger.warning("Could not persist evaluation: %s", exc)

    return response


def _get_patient_data(patient_id: str) -> dict | None:
    try:
        from db.database import get_patient_by_id
        return get_patient_by_id(patient_id)
    except Exception as exc:
        logger.warning("Could not fetch patient %s: %s", patient_id, exc)
        return None


def _build_patient_out(data: dict) -> PatientOut:
    return PatientOut(
        id=data["id"],
        display_name=data["display_name"],
        age=data["age"],
        sex=data["sex"],
        indication=data["indication"],
        cyp_profiles=[CypProfileOut(**p) for p in data.get("cyp_profiles", [])],
    )


async def _run_specialists(patient_id: str, medication: str) -> list[SpecialistOpinion]:
    from agents.rx_risk_agent import evaluate_rx_risk
    from agents.evidence_agent import retrieve_evidence
    from agents.adherence_agent import evaluate_adherence
    from agents.misuse_agent import evaluate_misuse_risk
    from agents.cost_navigator_agent import evaluate_cost

    phenotype = await _get_phenotype_from_patient(patient_id)

    results = await asyncio.gather(
        evaluate_rx_risk(patient_id, medication),
        retrieve_evidence(medication, phenotype),
        evaluate_adherence(patient_id, medication),
        evaluate_misuse_risk(patient_id, medication),
        evaluate_cost(patient_id, medication),
    )
    return list(results)


async def _get_phenotype_from_patient(patient_id: str) -> str:
    try:
        from agents.mcp_client import call_tool as _mcp_call
        from pgx.patients import extract_phenotype
        data = await _mcp_call("query_patient", {"patient_id": patient_id})
        return extract_phenotype(data)
    except Exception:
        return "unknown"


def _adjudicate(opinions: list[SpecialistOpinion], patient_id: str, medication: str) -> dict:
    if _groq and os.environ.get("GROQ_API_KEY"):
        try:
            return _llm_adjudicate(opinions)
        except Exception as exc:
            logger.warning("LLM adjudication failed, using deterministic: %s", exc)

    return _deterministic_adjudicate(opinions, medication)


def _llm_adjudicate(opinions: list[SpecialistOpinion]) -> dict:
    opinions_json = json.dumps([o.model_dump() for o in opinions], indent=2)

    messages = [
        {"role": "system", "content": ADJUDICATOR_PROMPT},
        {"role": "user", "content": f"Synthesize these specialist opinions for final decision:\n\n{opinions_json}"},
    ]

    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.3,
    )

    content = response.choices[0].message.content or ""
    parsed = _parse_adjudication(content)
    if not parsed or "risk_level" not in parsed:
        raise ValueError(f"LLM returned unparseable adjudication: {content[:200]}")
    return parsed


def _deterministic_adjudicate(opinions: list[SpecialistOpinion], medication: str) -> dict:
    risk_levels = {"critical": 4, "high": 3, "moderate": 2, "low": 1}
    max_risk = "low"
    max_score = 0
    any_flagged = False

    for o in opinions:
        score = risk_levels.get(o.risk_level, 1)
        if score > max_score:
            max_score = score
            max_risk = o.risk_level
        if o.flagged:
            any_flagged = True

    is_blocked = any_flagged or max_score >= 3
    alternative = None
    alt_rationale = ""
    for o in opinions:
        if o.agent_name == "CostNavigator" and o.recommendation and o.recommendation != medication:
            alternative = o.recommendation
            alt_rationale = o.risk_summary
            break
    if not alternative:
        for o in opinions:
            if o.recommendation and "avoid" in o.recommendation.lower():
                alt_match = __import__("re").search(r"(Duloxetine|Pregabalin|Acetaminophen)", o.reasoning + " " + o.risk_summary)
                if alt_match:
                    alternative = alt_match.group(1)
                    alt_rationale = f"Recommended by {o.agent_name}: {o.risk_summary}"
                    break

    agent_labels = [o.agent_name for o in opinions]
    agent_risks = ", ".join(f"{a}={o.risk_level}" for a, o in zip(agent_labels, opinions))

    return {
        "risk_level": max_risk,
        "agent_verdict": "blocked" if is_blocked else "review_required",
        "clinical_narrative": f"5-agent evaluation: {agent_risks}. {'BLOCKED' if is_blocked else 'Review required'}.",
        "recommended_alternative": alternative,
        "alternative_rationale": alt_rationale or "No alternative identified.",
        "decision_confidence": round(sum(o.confidence for o in opinions) / len(opinions), 2) if opinions else 0.8,
        "safety_notes": [],
    }


def _parse_adjudication(text: str) -> dict:
    import re
    if not text:
        return {}
    json_match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _build_agent_steps(opinions: list[SpecialistOpinion], start_time: float) -> list[AgentStep]:
    steps = []
    for o in opinions:
        steps.append(AgentStep(
            agent=o.agent_name,
            status="complete",
            summary=o.risk_summary[:200] if o.risk_summary else f"{o.agent_name} evaluation complete",
            duration_ms=0,
            confidence=o.confidence,
            evidence_refs=o.evidence_refs,
        ))
    steps.append(AgentStep(
        agent="HumanGate",
        status="pending",
        summary="Clinician approval required before release.",
        duration_ms=0,
        confidence=1.0,
        evidence_refs=["human_review"],
    ))
    return steps


def _build_evidence_summary(opinions: list[SpecialistOpinion]) -> str:
    parts = []
    for o in opinions:
        refs = ", ".join(o.evidence_refs) if o.evidence_refs else "no sources"
        parts.append(f"[{o.agent_name}] Sources: {refs} | {o.risk_summary}")
    return "\n".join(parts)


def _build_audit_trail(opinions: list[SpecialistOpinion]) -> list[AuditEvent]:
    return [
        AuditEvent(
            stage=o.agent_name,
            decision="blocked" if o.flagged else "cleared",
            rationale=o.risk_summary,
            requires_human_review=o.flagged,
        )
        for o in opinions
    ]


def _build_logic_tree(opinions: list[SpecialistOpinion]) -> dict:
    children = []
    for o in opinions:
        children.append({
            "node": o.agent_name,
            "detail": o.risk_summary[:150],
            "flag": o.flagged,
        })
    children.append({
        "node": "Human Gate",
        "detail": "Clinician approval required before release.",
        "flag": True,
    })
    return {"node": "Multi-Agent Orchestrator", "children": children}
```

---

### orchestrator.py (5 lines)

Thin re-export — only exposes `evaluate_prescription`.

```python
from __future__ import annotations

from agents.orchestrator_agent import evaluate_prescription

__all__ = ["evaluate_prescription"]
```

---

## Part IV: Specialist Agents

### rx_risk_agent.py (107 lines)

Drug-gene interaction risk specialist. Async with Groq LLM + deterministic fallback. Calls MCP tools `query_patient` and `query_drug_db` through `_mcp_call` in fallback.

```python
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are an Rx Risk Specialist — a pharmacogenomic drug-gene interaction expert.

YOUR ROLE: Evaluate whether a prescribed drug is safe for a specific patient based on their genetic profile.

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status, alternatives (input: medication)

PROCESS:
1. Call query_patient to get the patient's CYP phenotype
2. Call query_drug_db to get the drug's properties
3. Determine risk:
   - Ultra-Rapid Metabolizer (UM) + prodrug -> HIGH risk (toxicity — drug converts too fast)
   - Poor Metabolizer (PM) + prodrug -> HIGH risk (no therapeutic effect)
   - Normal Metabolizer (NM) -> LOW risk
   - Any + non-prodrug -> MODERATE risk (monitor)
4. Recommend alternative if risk is high

MANDATORY:
- Never fabricate data — only use tool results
- Always cite evidence
- Require human review for high/critical risk

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high" | "critical",
  "flagged": true/false,
  "risk_summary": "Brief explanation",
  "recommendation": "Avoid" | "Use with caution" | "Standard dosing",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="RxRisk",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_rx_risk(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="RxRisk",
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        user_message=f"Evaluate {medication} for patient {patient_id}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("RxRisk", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    is_prodrug = "prodrug" in drug_data.lower()
    pheno = extract_phenotype(patient_data)
    is_um = pheno == "ultra-rapid metabolizer"
    is_pm = pheno == "poor metabolizer"

    if is_um and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"Ultra-rapid metabolizer + prodrug ({medication}) -> risk of toxicity"
    elif is_pm and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"Poor metabolizer + prodrug ({medication}) -> no therapeutic effect"
    else:
        risk = "low"
        flagged = False
        summary = f"Standard risk profile for {medication}"

    return SpecialistOpinion(
        agent_name="RxRisk",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Avoid" if flagged else "Standard dosing",
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )
```

---

### evidence_agent.py (102 lines)

RAG evidence retrieval specialist. Groq LLM with tool calls to `query_evidence` and `search_knowledge`, with deterministic fallback using source filename extraction.

```python
from __future__ import annotations

import asyncio
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
        tools=[],
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
```

---

### adherence_agent.py (121 lines)

Adherence risk prediction specialist. Groq LLM + deterministic fallback. The fallback checks drug enzyme — non-CYP drugs bypass phenotype rules entirely, matching CPIC guidance.

```python
from __future__ import annotations

import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype as _extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are an Adherence Monitoring Specialist — you predict whether a patient is likely to adhere to a prescribed medication based on their genetic profile.

YOUR ROLE: Given a patient's CYP phenotype and a specific drug, assess the realistic adherence risk. Consider:
- Whether the drug is a prodrug (requires metabolic activation)
- Whether the patient's phenotype will cause unpleasant side effects (UM + prodrug -> toxicity)
- Whether the patient will feel NO benefit (PM + prodrug -> no effect -> abandonment)
- Whether the drug is even metabolized by the patient's relevant CYP enzyme
- If the drug is NOT CYP-metabolized, phenotype is irrelevant — standard adherence applies

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status (input: medication)
- lookup_patient_history: Get past adherence and evaluation history (input: patient_id)

MANDATORY:
- Never fabricate data — only use tool results
- If the drug is NOT metabolized by the patient's CYP enzymes, set risk to "low"
- A patient who feels NO benefit (PM + prodrug) has the HIGHEST non-adherence risk
- A patient who feels toxicity (UM + prodrug) has MODERATE non-adherence risk
- Always cite evidence
- Require human review for high/moderate risk

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high",
  "flagged": true/false,
  "risk_summary": "Brief explanation of adherence risk",
  "recommendation": "Intervention recommendation",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="Adherence",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_adherence(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="Adherence",
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        user_message=f"Evaluate adherence risk for patient {patient_id} taking {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("Adherence", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    phenotype = _extract_phenotype(patient_data)
    is_prodrug = "Is prodrug: True" in drug_data
    pheno_key = phenotype.lower() if phenotype else ""

    drug_enzyme = ""
    try:
        parsed = json.loads(drug_data)
        inner = parsed.get("result", drug_data)
    except (json.JSONDecodeError, TypeError):
        inner = str(drug_data)
    for line in inner.split("\n"):
        if line.startswith("Enzyme:"):
            drug_enzyme = line.split(":", 1)[1].strip()
            break

    if drug_enzyme in ("", "—"):
        risk = "low"
        flagged = False
        summary = f"{medication} is not CYP-metabolized. Standard adherence applies."
    elif pheno_key == "ultra-rapid metabolizer" and is_prodrug:
        risk = "moderate"
        flagged = True
        summary = f"UM + prodrug: potential toxicity side effects may reduce adherence."
    elif pheno_key == "poor metabolizer" and is_prodrug:
        risk = "high"
        flagged = True
        summary = f"PM + prodrug: no therapeutic effect — highest abandonment risk."
    else:
        risk = "low"
        flagged = False
        summary = f"Standard adherence risk for {medication} in {phenotype}."

    return SpecialistOpinion(
        agent_name="Adherence",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Monitor adherence" if flagged else "Standard monitoring",
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )
```

---

### misuse_agent.py (111 lines)

Misuse/abuse risk detection. Pure deterministic — only `UM + prodrug opioid` returns `high/flagged=True`; everything else is `low`. Matches CPIC Level A evidence and FDA black box warning.

```python
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from agents.base import log_risk_discrepancy, run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype as _extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are a Misuse Monitoring Specialist — you detect prescription misuse risk based on genetics and drug pharmacology.

YOUR ROLE: Given a patient's CYP phenotype and a specific drug, assess the potential for misuse, abuse, or diversion. Use the query_clinical_guideline tool to get the evidence-based recommendation for each drug-phenotype pair.

CRITICAL GUIDELINES — only these evidence-supported cases warrant flagged=True:
- UM + prodrug opioid (Codeine, Tramadol) = HIGH risk — FDA black box warning for life-threatening respiratory depression
- All other combinations = LOW risk with standard monitoring

For all other cases (NM, IM, PM with any opioid; non-prodrug opioids; non-opioids):
- The evidence does not support PGx-driven flagging
- Return risk_level="low" and flagged=False with standard monitoring recommendation
- NM patients should receive standard dosing per CPIC

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including enzyme, prodrug status (input: medication)
- lookup_patient_history: Get past adherence and evaluation history (input: patient_id)
- query_clinical_guideline: Get CPIC/DPWG evidence-based recommendation for a drug-phenotype pair (input: drug, phenotype)

MANDATORY:
- Never fabricate data — only use tool results
- Call query_clinical_guideline BEFORE making your assessment
- Non-opioid drugs should always be LOW risk
- UM + prodrug opioid (Codeine, Tramadol) = HIGH risk, flagged=True
- All other combinations = LOW risk, flagged=False
- Always cite evidence

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate" | "high",
  "flagged": true/false,
  "risk_summary": "Brief explanation of misuse risk",
  "recommendation": "Clinical recommendation for monitoring",
  "reasoning": "Step-by-step reasoning",
  "confidence": 0.0-1.0
}"""


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="MisuseMonitor",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_misuse_risk(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="MisuseMonitor",
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        user_message=f"Evaluate misuse risk for patient {patient_id} taking {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        consistency_check=log_risk_discrepancy("MisuseMonitor", patient_id, medication),
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    phenotype = _extract_phenotype(patient_data)
    is_prodrug = "Is prodrug: True" in drug_data
    is_opioid = any(d in medication.lower() for d in ["codeine", "tramadol", "hydrocodone", "oxycodone", "morphine", "fentanyl"])
    pheno_lower = phenotype.lower() if phenotype else ""

    if not is_opioid:
        risk = "low"
        flagged = False
        summary = f"{medication} is not an opioid. Standard prescribing risk applies."
    elif is_prodrug and pheno_lower == "ultra-rapid metabolizer":
        risk = "high"
        flagged = True
        summary = f"UM + prodrug opioid: rapid conversion creates euphoric peak. HIGH misuse risk (FDA black box)."
    else:
        risk = "low"
        flagged = False
        summary = f"Standard opioid monitoring for {phenotype} (CPIC: no PGx-driven flag)."

    return SpecialistOpinion(
        agent_name="MisuseMonitor",
        risk_level=risk,
        flagged=flagged,
        risk_summary=summary,
        recommendation="Strict monitoring agreement" if flagged else "Standard monitoring",
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )
```

---

### cost_navigator_agent.py (119 lines)

Cost-effective alternative finder. Groq LLM + deterministic fallback. Uses `_clamp_cost_opinion` to prevent the cost agent from ever setting `flagged=True` or `risk_level > moderate` (business logic constraint — cost should not override clinical safety).

```python
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from agents.base import run_specialist_agent
from agents.mcp_client import call_tool as _mcp_call
from models import SpecialistOpinion
from pgx.patients import extract_phenotype as _extract_phenotype

logger = logging.getLogger(__name__)
load_dotenv()

SYSTEM_PROMPT = """You are a Cost Navigator Specialist — you find affordable, phenotype-safe therapeutic alternatives based on patient genetics and drug properties.

YOUR ROLE: Given a patient's CYP phenotype and a prescribed drug, recommend cost-effective alternatives that are safe for their genetic profile. Consider:
- Prodrugs in UM patients cause toxicity -> avoid -> switch to non-prodrug alternative
- Prodrugs in PM patients cause no effect -> avoid -> switch to non-prodrug alternative
- Non-prodrug drugs in any phenotype -> generally safe, standard cost considerations
- Alternatives should be phenotype-safe AND cost-effective (fewer adverse events = lower total cost)
- If the drug has no known alternatives, note that clearly

AVAILABLE TOOLS:
- query_patient: Get patient CYP genotype and phenotype (input: patient_id)
- query_drug_db: Get drug PGx properties including alternatives (input: medication)
- query_alternative_drugs: Get structured alternative drug options (input: drug, phenotype)

MANDATORY:
- Never fabricate data — only use tool results
- Always explain WHY an alternative is more cost-effective
- If no alternatives exist, state "no alternatives identified" — do not make up drugs
- Always cite evidence

Return your final assessment as JSON:
{
  "risk_level": "low" | "moderate",
  "flagged": true/false,
  "risk_summary": "Cost analysis summary with alternative recommendation",
  "recommendation": "Preferred alternative drug name or current drug if none found",
  "reasoning": "Step-by-step cost-effectiveness reasoning",
  "confidence": 0.0-1.0
}"""


def _clamp_cost_opinion(opinion: dict) -> dict:
    clamped = dict(opinion)
    clamped["flagged"] = False
    raw_risk = clamped.get("risk_level", "low")
    clamped["risk_level"] = raw_risk if raw_risk in ("low", "moderate") else "low"
    return clamped


def _build_opinion(parsed: dict, tool_calls_made: list[str], tool_results_raw: list[str], msg_content: str) -> SpecialistOpinion:
    return SpecialistOpinion(
        agent_name="CostNavigator",
        risk_level=parsed.get("risk_level", "low"),
        flagged=parsed.get("flagged", False),
        risk_summary=parsed.get("risk_summary", ""),
        recommendation=parsed.get("recommendation", ""),
        reasoning=parsed.get("reasoning", msg_content),
        confidence=parsed.get("confidence", 0.8),
        evidence_refs=tool_calls_made,
    )


async def evaluate_cost(patient_id: str, medication: str) -> SpecialistOpinion:
    return await run_specialist_agent(
        agent_name="CostNavigator",
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        user_message=f"Find cost-effective alternatives for patient {patient_id} prescribed {medication}",
        build_opinion=_build_opinion,
        fallback=lambda: _fallback(patient_id, medication),
        post_process=_clamp_cost_opinion,
    )


async def _fallback(patient_id: str, medication: str) -> SpecialistOpinion:
    patient_data = await _mcp_call("query_patient", {"patient_id": patient_id})
    drug_data = await _mcp_call("query_drug_db", {"medication": medication})

    phenotype = _extract_phenotype(patient_data)
    is_prodrug = "prodrug" in drug_data.lower()
    alternatives = _extract_alternatives(drug_data)

    preferred_alt = alternatives[0] if alternatives else None

    if preferred_alt and is_prodrug and "ultra-rapid" in phenotype.lower():
        summary = (
            f"Switch from {medication} to {preferred_alt}. "
            f"UM + prodrug causes toxicity-related costs; {preferred_alt} is phenotype-safe."
        )
    elif preferred_alt:
        summary = f"{preferred_alt} is a cost-effective alternative for {medication}."
    else:
        summary = f"No cost-effective alternative identified for {medication}."

    return SpecialistOpinion(
        agent_name="CostNavigator",
        risk_level="low",
        flagged=False,
        risk_summary=summary,
        recommendation=preferred_alt or medication,
        reasoning=f"Fallback deterministic evaluation.\nPatient: {patient_data}\nDrug: {drug_data}",
        confidence=0.7,
        evidence_refs=["query_patient", "query_drug_db"],
    )


def _extract_alternatives(drug_data: str) -> list[str]:
    import re
    alt_section = re.search(r"Alternatives:\s*(.+)", drug_data)
    if alt_section:
        alts = alt_section.group(1).strip()
        return [a.strip() for a in alts.split(",") if a.strip() and a.strip() != "None"]
    return []
```

---

## Part V: Shared Tool Registry

### tools.py (291 lines)

The `@register` decorator-based tool framework. All agent-facing tools (query_patient, query_drug_db, search_knowledge, etc.) are registered here. MCP servers wrap these same functions. Both MCP and direct call paths converge here.

```python
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]


_registry: dict[str, Tool] = {}


def register(name: str | None = None, description: str | None = None):
    """Decorator that registers a function as a callable tool."""
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        properties: dict[str, dict[str, str]] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            properties[param_name] = {"type": "string", "description": f"Parameter: {param_name}"}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        t = Tool(
            name=name or fn.__name__,
            description=description or fn.__doc__ or "",
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            fn=fn,
        )
        _registry[t.name] = t
        return fn

    return decorator


def get_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _registry.values()
    ]


def list_tools() -> list[str]:
    return sorted(_registry.keys())


# --- Built-in tools ---

@register(description="Look up drug pharmacology and PGx information from the drug database.")
def query_drug_db(medication: str) -> str:
    from pgx.rules import DRUG_RULES, normalize_medication

    normalized = normalize_medication(medication)
    if not normalized:
        return f"Drug '{medication}' not found in the demo formulary."

    rule = DRUG_RULES.get(normalized)
    if not rule:
        return f"No PGx rule found for '{normalized}'."

    return (
        f"Drug: {rule.name}\n"
        f"Enzyme: {rule.enzyme}\n"
        f"Pathway: {rule.pathway}\n"
        f"Is prodrug: {rule.is_prodrug}\n"
        f"Alternatives: {', '.join(rule.alternatives) if rule.alternatives else 'None'}\n"
        f"CPIC level: {rule.cpic_level.value}\n"
        f"CPIC note: {rule.cpic_note}"
    )


@register(description="Retrieve a patient's past evaluation history and prescribing trends.")
def lookup_patient_history(patient_id: str) -> str:
    from db.database import list_evaluations

    evals = list_evaluations(patient_id.upper())
    if not evals:
        return f"No evaluation history found for patient '{patient_id}'."

    lines = [f"Patient: {patient_id}", f"Total evaluations: {len(evals)}", ""]
    for e in evals[-5:]:
        lines.append(f"- {e.get('medication', '?')}: {e.get('risk_level', '?')} (flagged={e.get('flagged', '?')})")
    return "\n".join(lines)


@register(description="Search the clinical knowledge base for pharmacogenomic evidence using semantic search.")
def search_knowledge(query: str) -> str:
    from db.vector_store import query_clinical_knowledge

    results = query_clinical_knowledge(query, top_k=3, min_similarity=0.3)
    if not results:
        return "No relevant knowledge found."

    lines = [f"Found {len(results)} relevant results:", ""]
    for r in results:
        lines.append(f"[{r['source']}] (confidence: {r['similarity']:.2f})")
        lines.append(f"  {r['text'][:200]}")
        lines.append("")
    return "\n".join(lines)


@register(description="Get information about a specific CYP phenotype and its clinical implications.")
def get_phenotype_info(phenotype: str) -> str:
    info = {
        "ultra-rapid metabolizer": "Increased enzyme activity. Risk of toxicity with prodrugs due to excessive active metabolite formation.",
        "poor metabolizer": "Reduced or absent enzyme activity. Risk of treatment failure with prodrugs; increased side effect risk with some drugs.",
        "intermediate metabolizer": "Reduced enzyme activity. May require dose adjustment for some medications.",
        "normal metabolizer": "Normal enzyme activity. Standard dosing applies.",
    }
    key = phenotype.lower().strip()
    for pattern, desc in info.items():
        if pattern in key:
            return f"{phenotype}: {desc}"
    return f"Phenotype '{phenotype}' not found in reference database."


@register(description="Calculate estimated renal function (eGFR) using the Cockcroft-Gault formula.")
def calculate_egfr(age: str, sex: str, creatinine: str, weight_kg: str = "70") -> str:
    try:
        age_val = float(age)
        creat_val = float(creatinine)
        weight_val = float(weight_kg)
    except ValueError:
        return "Error: age, creatinine, and weight_kg must be numeric."

    if creat_val <= 0:
        return "Error: creatinine must be positive."

    crcl = ((140 - age_val) * weight_val) / (72 * creat_val)
    if sex.lower().startswith("f"):
        crcl *= 0.85

    return f"Estimated CrCl: {crcl:.1f} mL/min (Cockcroft-Gault)"


# --- Agent-specific tool dispatcher ---


def execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    import json

    if name == "query_patient":
        return _tool_query_patient(tool_input.get("patient_id", ""))
    elif name == "query_evidence":
        return _tool_query_evidence(
            tool_input.get("drug", ""), tool_input.get("phenotype", "")
        )
    elif name == "query_alternative_drugs":
        return _tool_query_alternative_drugs(
            tool_input.get("drug", ""), tool_input.get("phenotype", "")
        )

    # Fall back to registry-based tools
    if name not in _registry:
        return json.dumps({"error": f"Tool '{name}' not found"})
    try:
        result = _registry[name].fn(**tool_input)
        return json.dumps({"result": str(result)})
    except Exception as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return json.dumps({"error": f"Error executing '{name}': {exc}"})


def _tool_query_patient(patient_id: str) -> str:
    """Query patient genetic profile and phenotype."""
    import json

    try:
        from db.database import get_patient_by_id
        from agents.research import research_patient

        patient, summary, _ = research_patient(patient_id)
        if not patient:
            return json.dumps({"error": f"Patient '{patient_id}' not found"})

        return json.dumps(
            {
                "patient_id": patient.get("id"),
                "display_name": patient.get("display_name"),
                "age": patient.get("age"),
                "sex": patient.get("sex"),
                "indication": patient.get("indication"),
                "cyp_profiles": patient.get("cyp_profiles", []),
                "clinical_history": summary,
            }
        )
    except Exception as exc:
        logger.error("query_patient failed: %s", exc)
        return json.dumps({"error": f"Failed to query patient: {exc}"})


def _tool_query_evidence(drug: str, phenotype: str) -> str:
    """Query clinical evidence for drug-phenotype interaction."""
    import json

    try:
        from agents.therapy_rag import retrieve_therapy_evidence

        evidence, _ = retrieve_therapy_evidence(
            drug, {"phenotype": phenotype}
        )
        return json.dumps(evidence)
    except Exception as exc:
        logger.error("query_evidence failed: %s", exc)
        return json.dumps({"error": f"Failed to query evidence: {exc}"})


def _tool_query_alternative_drugs(drug: str, phenotype: str) -> str:
    """Query alternative medications for given drug-phenotype pair."""
    import json

    try:
        from pgx.rules import DRUG_RULES, normalize_medication

        normalized = normalize_medication(drug)
        if not normalized:
            return json.dumps(
                {
                    "alternatives": [],
                    "reason": f"'{drug}' not in demo formulary",
                }
            )

        rule = DRUG_RULES.get(normalized)
        if not rule or not rule.alternatives:
            return json.dumps({"alternatives": [], "reason": "No alternatives found"})

        phenotype_lower = phenotype.lower()
        alternatives = []
        for alt in rule.alternatives:
            alt_rule = DRUG_RULES.get(alt.lower())
            if alt_rule:
                alternatives.append(
                    {
                        "drug": alt,
                        "enzyme": alt_rule.enzyme,
                        "is_prodrug": alt_rule.is_prodrug,
                        "cpic_note": alt_rule.cpic_note,
                    }
                )

        return json.dumps(
            {
                "alternatives": alternatives,
                "reason": f"Evidence-backed alternatives for {drug} in {phenotype}",
            }
        )
    except Exception as exc:
        logger.error("query_alternative_drugs failed: %s", exc)
        return json.dumps({"error": f"Failed to query alternatives: {exc}"})
```

---

## Part VI: RAG Evidence Retrieval

### therapy_rag.py (248 lines)

Dual-mode RAG engine: semantic search (ChromaDB) first, falls back to keyword retrieval. Returns source-grounded evidence with quality scoring. Used by `_tool_query_evidence`.

```python
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from db.vector_store import query_clinical_knowledge

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

SIMILARITY_THRESHOLD = 0.25
HIGH_QUALITY_THRESHOLD = 0.5
MODERATE_QUALITY_THRESHOLD = 0.35

CORE_TERMS = {
    "mrna", "therapy", "target", "candidate",
    "sequence", "validation", "safety", "human",
    "review", "research", "simulation",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _snippet(text: str, limit: int = 360) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _load_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts = [part.strip() for part in re.split(r"\n(?=## |\# )", text) if part.strip()]
        for index, part in enumerate(parts):
            chunks.append({
                "source": path.name,
                "chunk_id": f"{path.name}:{index + 1}",
                "text": part,
            })
    return chunks


def _score_chunk(chunk: dict[str, Any], query_terms: set[str]) -> int:
    chunk_terms = _tokenize(chunk["text"])
    source_terms = _tokenize(chunk["source"].replace("_", " "))
    overlap = len(query_terms & chunk_terms)
    core_overlap = len(CORE_TERMS & chunk_terms)
    source_overlap = len(query_terms & source_terms)
    return (overlap * 3) + core_overlap + source_overlap


def _fallback_keyword_retrieval(
    target_disease: str,
    patient_context: dict[str, Any],
    start_time: float,
) -> tuple[dict[str, Any], int]:
    stop_terms = {
        "disease", "research", "simulation", "therapy",
        "target", "patient", "clinical",
    }
    disease_terms = _tokenize(target_disease) - stop_terms

    phenotype_terms = {
        profile.get("phenotype", "")
        for profile in patient_context.get("cyp_profiles", [])
        if isinstance(profile, dict)
    }
    general_terms = _tokenize(
        "mRNA therapy target validation safety human review research simulation"
    )
    query_terms = (
        _tokenize(target_disease)
        | _tokenize(patient_context.get("indication", ""))
        | _tokenize(" ".join(phenotype_terms))
        | general_terms
    )

    chunks = _load_chunks()
    ranked = []
    for chunk in chunks:
        score = _score_chunk(chunk, query_terms)
        disease_overlap = (
            len(disease_terms & _tokenize(chunk["text"])) if disease_terms else 0
        )
        score += disease_overlap * 20
        if score > 0:
            ranked.append((score, chunk, disease_overlap))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:5]

    if not selected:
        return _low_quality_response(start_time)

    sources = sorted({chunk["source"] for _, chunk, _ in selected})
    total_disease_overlap = sum(d for _, _, d in selected)
    policy_present = any("n_of_1" in source for source in sources)

    if disease_terms and total_disease_overlap < 1:
        return _low_quality_response(start_time)

    if total_disease_overlap >= 3:
        evidence_quality = (
            "high" if len(sources) >= 2 and policy_present else "moderate"
        )
    elif total_disease_overlap >= 1 or not disease_terms:
        evidence_quality = "moderate"
    else:
        return _low_quality_response(start_time)

    elapsed = int((time.perf_counter() - start_time) * 1000)
    return (
        {
            "sources": sources,
            "target_rationale": (
                f"Retrieved {len(selected)} source chunks for {target_disease}. "
                "The evidence supports a simulated research candidate and "
                "requires human review."
            ),
            "known_risks": [
                "The candidate is not clinically validated.",
                "Sequence validation is deterministic but still a simulation.",
                "Disease-specific target evidence may be incomplete.",
            ],
            "open_questions": [
                "Is the target disease mechanism sufficiently documented?",
                "Does the reviewer accept the validation thresholds?",
            ],
            "evidence_quality": evidence_quality,
            "source_snippets": [
                {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                    "score": score,
                    "snippet": _snippet(chunk["text"]),
                }
                for score, chunk, _ in selected
            ],
        },
        elapsed,
    )


def retrieve_therapy_evidence(
    target_disease: str,
    patient_context: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Retrieve source-grounded context using semantic search + deterministic guardrails."""
    start = time.perf_counter()

    phenotype_terms = " ".join(
        profile.get("phenotype", "")
        for profile in patient_context.get("cyp_profiles", [])
        if isinstance(profile, dict)
    )
    query = f"{target_disease} {patient_context.get('indication', '')} {phenotype_terms} mRNA therapy candidate validation"

    semantic_hits = query_clinical_knowledge(
        query, top_k=5, min_similarity=SIMILARITY_THRESHOLD
    )

    if semantic_hits:
        sources = sorted({h["source"] for h in semantic_hits})
        total_similarity = sum(h["similarity"] for h in semantic_hits)
        avg_similarity = total_similarity / len(semantic_hits)
        policy_present = any("n_of_1" in source for source in sources)

        if avg_similarity >= HIGH_QUALITY_THRESHOLD and len(sources) >= 2 and policy_present:
            evidence_quality = "high"
        elif avg_similarity >= MODERATE_QUALITY_THRESHOLD:
            evidence_quality = "moderate"
        else:
            evidence_quality = "low"

        disease_terms = _tokenize(target_disease)
        disease_overlap = sum(
            len(disease_terms & _tokenize(h["text"])) for h in semantic_hits
        )
        if disease_terms and disease_overlap < 1:
            return _low_quality_response(start)

        elapsed = int((time.perf_counter() - start) * 1000)
        return (
            {
                "sources": sources,
                "target_rationale": (
                    f"Semantic retrieval returned {len(semantic_hits)} relevant chunks "
                    f"(avg similarity={avg_similarity:.2f}) for {target_disease}. "
                    "The evidence supports a simulated research candidate and "
                    "requires human review."
                ),
                "known_risks": [
                    "The candidate is not clinically validated.",
                    "Sequence validation is deterministic but still a simulation.",
                    "Disease-specific target evidence may be incomplete.",
                ],
                "open_questions": [
                    "Is the target disease mechanism sufficiently documented?",
                    "Does the reviewer accept the validation thresholds?",
                ],
                "evidence_quality": evidence_quality,
                "source_snippets": [
                    {
                        "source": h["source"],
                        "chunk_id": h["chunk_id"],
                        "score": h["similarity"],
                        "snippet": _snippet(h["text"]),
                    }
                    for h in semantic_hits
                ],
            },
            elapsed,
        )

    logger.warning("Semantic retrieval returned no hits, falling back to keyword")
    return _fallback_keyword_retrieval(target_disease, patient_context, start)


def _low_quality_response(start_time: float) -> tuple[dict[str, Any], int]:
    elapsed = int((time.perf_counter() - start_time) * 1000)
    return (
        {
            "sources": [],
            "target_rationale": (
                "No disease-specific evidence was retrieved. The system cannot "
                "reliably identify a therapeutic target for this indication."
            ),
            "known_risks": ["Insufficient source grounding for target selection."],
            "open_questions": [
                "Which reviewed disease mechanism supports this target?"
            ],
            "evidence_quality": "low",
            "source_snippets": [],
        },
        elapsed,
    )
```


---

## Part VIII: Independent Adherence Monitoring

### adherence.py (137 lines)

Separate from `adherence_agent.py`. Handles ongoing patient check-ins (day 3, day 7), triage, and empathetic replies. Uses Groq LLM for triage + reply generation, with deterministic fallback.

```python
from __future__ import annotations

import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from config import GROQ_MODEL
from db.database import create_adherence_plan, get_adherence_plan, submit_check_in

logger = logging.getLogger(__name__)

try:
    load_dotenv()
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


def start_adherence_monitoring(patient_id: str, medication: str) -> dict:
    plan = create_adherence_plan(patient_id, medication)
    if not plan:
        return {"status": "error", "message": "Could not create adherence plan"}
    return {
        "status": "success",
        "plan_id": plan["id"],
        "patient_id": patient_id.upper(),
        "medication": medication,
        "check_ins": plan.get("check_ins") or _fetch_check_ins(plan["id"]),
        "message": (
            f"Adherence monitoring started for {medication}. "
            "Check-ins scheduled for day 3 and day 7."
        ),
    }


def _fetch_check_ins(plan_id: str) -> list:
    full = get_adherence_plan(plan_id)
    return full.get("check_ins", []) if full else []


async def process_check_in(
    check_in_id: str, response: str, side_effect_reported: bool
) -> dict:
    updated = submit_check_in(check_in_id, response, side_effect_reported)
    if not updated:
        return {"status": "error", "message": "Check-in not found"}

    triage = await _perform_clinical_triage(response, side_effect_reported)
    empathetic = await _optional_empathetic_reply(response, side_effect_reported)

    return {
        "status": "success",
        "check_in": updated,
        "side_effect_reported": side_effect_reported,
        "triage": triage,
        "empathetic_reply": empathetic,
    }


async def _perform_clinical_triage(response: str, side_effect: bool) -> dict:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        severity = "MEDIUM" if side_effect else "LOW"
        action = "Review PGx profile" if side_effect else "Continue monitoring"
        return {"severity": severity, "action": action, "rationale": "Rule-based fallback used."}

    try:
        completion = await asyncio.to_thread(
            _groq.chat.completions.create,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a clinical pharmacogenomics triage agent. "
                        "Analyze the patient response and side-effect flag. "
                        "Return ONLY a JSON object with: severity (LOW, MEDIUM, HIGH, CRITICAL), "
                        "action (short clinical directive), and rationale (brief explanation). "
                        "Synthetic demo data only."
                    ),
                },
                {"role": "user", "content": f"Response: {response}. Side effect: {side_effect}"},
            ],
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.warning(f"Triage LLM failure: {e}", exc_info=True)
        return {"severity": "MEDIUM" if side_effect else "LOW", "action": "Clinician review recommended", "rationale": "Triage service error fallback."}


async def _optional_empathetic_reply(response: str, side_effect: bool) -> str | None:
    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        if side_effect:
            return "Thank you for sharing that. Side effects can be difficult — your care team will review your profile and follow up soon."
        return "Thank you for the update. Keep taking your medication as prescribed unless your clinician advises otherwise."

    try:
        completion = await asyncio.to_thread(
            _groq.chat.completions.create,
            messages=[
                {
                    "role": "system",
                    "content": "You are an empathetic medication adherence assistant. Reply in 1-2 warm, brief sentences. Synthetic demo only.",
                },
                {"role": "user", "content": f"Patient said: {response}. Side effect reported: {side_effect}"},
            ],
            model=GROQ_MODEL,
            max_tokens=100,
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.warning(f"Empathetic reply LLM failure: {e}")
        return None
```

---

## Part IX: Clinical Note Reporter

### reporter.py (157 lines)

Clinical note generation: LLM-first (Groq) with fallback to structured SOAP template. Produces EHR-ready notes from `EvaluationResponse`.

```python
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
    try:
        if isinstance(evaluation_input, dict):
            evaluation = EvaluationResponse(**evaluation_input)
        else:
            evaluation = evaluation_input
    except Exception as e:
        return f"CRITICAL ERROR: Failed to parse evaluation data. {e}"

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

        relevant_gene = "CYP2D6"
        phenotype = "Unknown"

        if patient and patient.cyp_profiles:
            for profile in patient.cyp_profiles:
                if profile.gene in risk_summary or any(profile.gene in p for p in evaluation.pathways):
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
                {"role": "system", "content": "You are a Senior Clinical Pharmacogeneticist. Your task is to provide a structured, formal EHR documentation entry."},
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
```
