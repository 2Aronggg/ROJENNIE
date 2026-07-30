"""Small Finance MCP client used by the agent data resolver.

`FINANCE_MCP_TRANSPORT=inprocess` keeps local development fast while still
using the same tool registry.  Set it to `stdio` to exercise the real MCP
protocol and spawn ``python -m server.mcp_finance`` for each tool call.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from server.mock_data import MockBankClient


class FinanceMCPError(RuntimeError):
    pass


class FinanceMCPClient:
    """Adapter exposing the old read-client shape through Finance MCP tools."""

    def __init__(self, *, transport: str | None = None, customer_ref: str = "session-user") -> None:
        self.transport = (transport or os.getenv("FINANCE_MCP_TRANSPORT", "inprocess")).strip().lower()
        if self.transport not in {"inprocess", "stdio"}:
            raise ValueError("FINANCE_MCP_TRANSPORT must be inprocess or stdio")
        self.customer_ref = customer_ref

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        args = dict(arguments or {})
        if name.startswith("get_my_"):
            args.setdefault("customer_ref", self.customer_ref)
        if self.transport == "inprocess":
            from server.mcp_finance import call_finance_tool

            return call_finance_tool(name, args)
        return asyncio.run(self._call_stdio(name, args))

    def source_ref(self, tool: str) -> str:
        return f"mcp://finance/{tool}"

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        profile = self.call_tool("get_my_profile")
        return profile if profile.get("customer_id") == customer_id else None

    def get_products(self, customer_id: str) -> dict[str, list[dict[str, Any]]]:
        self._assert_customer(customer_id)
        return self.call_tool("get_my_products")

    def get_deposits(self, customer_id: str) -> list[dict[str, Any]]:
        self._assert_customer(customer_id)
        return self.call_tool("get_my_deposits")

    def get_savings(self, customer_id: str) -> list[dict[str, Any]]:
        self._assert_customer(customer_id)
        return self.call_tool("get_my_savings")

    def get_loans(self, customer_id: str) -> list[dict[str, Any]]:
        self._assert_customer(customer_id)
        return self.call_tool("get_my_loans")

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        for method in ("get_my_deposits", "get_my_savings", "get_my_loans"):
            account = next((item for item in self.call_tool(method) if item.get("account_id") == account_id), None)
            if account is not None:
                return account
        return None

    def get_transactions(self, account_id: str) -> list[dict[str, Any]]:
        return self.call_tool("get_my_transactions", {"account_id": account_id})

    def get_repayments(self, account_id: str) -> list[dict[str, Any]]:
        return self.call_tool("get_my_repayments", {"account_id": account_id})

    def get_rate_history(self, account_id: str) -> list[dict[str, Any]]:
        return self.call_tool("get_my_rate_history", {"account_id": account_id})

    def get_notice_history(self, account_id: str) -> list[dict[str, Any]]:
        return self.call_tool("get_my_notice_history", {"account_id": account_id})

    def _assert_customer(self, customer_id: str) -> None:
        profile = self.call_tool("get_my_profile")
        if profile.get("customer_id") != customer_id:
            raise FinanceMCPError("customer is not available in the current session")

    async def _call_stdio(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise FinanceMCPError("mcp package is required for stdio transport") from exc

        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "server.mcp_finance"],
            env=env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            raise FinanceMCPError(_text_result(result))
        structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
        if structured is not None:
            return structured.get("result", structured) if isinstance(structured, dict) else structured
        return _text_result(result)


def _text_result(result: Any) -> Any:
    texts: list[str] = []
    for content in getattr(result, "content", []) or []:
        text = getattr(content, "text", None)
        if text:
            texts.append(text)
    value = "\n".join(texts)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
