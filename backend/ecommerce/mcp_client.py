import json
import os
import sys
import asyncio
import time
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class EcommerceMCPClient:
    def __init__(self, database_url: str, project_root: Path | None = None, persistent: bool = False):
        self.database_url = database_url
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.persistent = persistent
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()
        self._failures = 0
        self._circuit_open_until = 0.0
        self.calls = 0
        self.total_latency_ms = 0.0

    def _parameters(self) -> StdioServerParameters:
        env = {**os.environ, "MCP_ECOMMERCE_DATABASE_URL": self.database_url, "PYTHONPATH": str(self.project_root)}
        return StdioServerParameters(command=sys.executable, args=["-m", "backend.mcp_servers.ecommerce_server"], cwd=str(self.project_root), env=env)

    async def start(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(self._parameters()))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._stack, self._session = stack, session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack, self._session = None, None

    async def _reset(self) -> None:
        try:
            await self.close()
        finally:
            if self.persistent:
                await self.start()

    @asynccontextmanager
    async def session(self):
        if self.persistent:
            await self.start()
            yield self._session
            return
        async with stdio_client(self._parameters()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self.session() as session:
            result = await session.list_tools()
            return [{"name": tool.name, "description": tool.description or "", "input_schema": tool.inputSchema} for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if time.monotonic() < self._circuit_open_until:
            raise RuntimeError("MCP circuit breaker is open")
        started = time.perf_counter()
        async with self._lock:
            try:
                async with self.session() as session:
                    result = await session.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=20))
                self._failures = 0
            except Exception:
                self._failures += 1
                if self._failures >= 3:
                    self._circuit_open_until = time.monotonic() + 30
                if self.persistent:
                    await self._reset()
                raise
            finally:
                self.calls += 1
                self.total_latency_ms += (time.perf_counter() - started) * 1000
        if result.isError:
            message = " ".join(getattr(item, "text", "") for item in result.content).strip()
            raise RuntimeError(message or f"MCP tool {name} failed")
        if result.structuredContent:
            payload = result.structuredContent
            return payload.get("result", payload) if isinstance(payload, dict) else payload
        text = next((getattr(item, "text", "") for item in result.content if getattr(item, "text", "")), "{}")
        return json.loads(text)

    def health(self) -> dict[str, Any]:
        return {"persistent": self.persistent, "connected": self._session is not None, "calls": self.calls, "average_latency_ms": round(self.total_latency_ms / self.calls, 2) if self.calls else 0, "failures": self._failures, "circuit_open": time.monotonic() < self._circuit_open_until}
