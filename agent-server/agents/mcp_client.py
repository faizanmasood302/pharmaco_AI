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
        self._tool_map: dict[str, str] = {}  # tool_name → server_name
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
