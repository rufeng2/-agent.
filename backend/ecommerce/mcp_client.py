import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class EcommerceMCPClient:
    def __init__(self, database_url: str, project_root: Path | None = None):
        self.database_url = database_url
        self.project_root = project_root or Path(__file__).resolve().parents[2]

    @asynccontextmanager
    async def session(self):
        env = {**os.environ, "MCP_ECOMMERCE_DATABASE_URL": self.database_url, "PYTHONPATH": str(self.project_root)}
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "backend.mcp_servers.ecommerce_server"], cwd=str(self.project_root), env=env)
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self.session() as session:
            result = await session.list_tools()
            return [{"name": tool.name, "description": tool.description or "", "input_schema": tool.inputSchema} for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with self.session() as session:
            result = await session.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=20))
        if result.isError:
            message = " ".join(getattr(item, "text", "") for item in result.content).strip()
            raise RuntimeError(message or f"MCP tool {name} failed")
        if result.structuredContent:
            payload = result.structuredContent
            return payload.get("result", payload) if isinstance(payload, dict) else payload
        text = next((getattr(item, "text", "") for item in result.content if getattr(item, "text", "")), "{}")
        return json.loads(text)
