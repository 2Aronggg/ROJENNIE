"""Finance MCP server backed by the demo bank database.

The server is read-only on purpose.  It exposes only the customer's own
profile, products, transactions, histories, and a deterministic calculator.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from mcp.server.fastmcp import FastMCP

from server.finance.mock_data import MockBankClient


mcp = FastMCP("finance", json_response=True)
_bank = MockBankClient()
_SESSION_CUSTOMERS = {"session-user": "CUST-001", "CUST-001": "CUST-001"}


def _customer_id(customer_ref: str) -> str:
    try:
        return _SESSION_CUSTOMERS[customer_ref]
    except KeyError as exc:
        raise ValueError("unknown customer session") from exc


def _account(account_id: str, customer_ref: str) -> dict[str, Any]:
    account = _bank.get_account(account_id)
    if not account or account.get("customer_id") != _customer_id(customer_ref):
        raise ValueError("account is not available in the current session")
    return account


@mcp.tool()
def get_my_profile(customer_ref: str = "session-user") -> dict[str, Any]:
    """Return the authenticated demo customer's profile and consent state."""
    customer = _bank.get_customer(_customer_id(customer_ref))
    if customer is None:
        raise ValueError("customer not found")
    return customer


@mcp.tool()
def get_my_products(customer_ref: str = "session-user") -> dict[str, list[dict[str, Any]]]:
    """Return the customer's deposit, savings, and loan product summaries."""
    return _bank.get_products(_customer_id(customer_ref))


@mcp.tool()
def get_my_deposits(customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return the customer's deposit contracts."""
    return _bank.get_deposits(_customer_id(customer_ref))


@mcp.tool()
def get_my_savings(customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return the customer's installment-savings contracts."""
    return _bank.get_savings(_customer_id(customer_ref))


@mcp.tool()
def get_my_loans(customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return the customer's loan contracts."""
    return _bank.get_loans(_customer_id(customer_ref))


@mcp.tool()
def get_my_transactions(account_id: str, customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return transactions for one of the customer's accounts."""
    _account(account_id, customer_ref)
    return _bank.get_transactions(account_id)


@mcp.tool()
def get_my_repayments(account_id: str, customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return loan repayments for one of the customer's accounts."""
    _account(account_id, customer_ref)
    return _bank.get_repayments(account_id)


@mcp.tool()
def get_my_rate_history(account_id: str, customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return rate changes for one of the customer's accounts."""
    _account(account_id, customer_ref)
    return _bank.get_rate_history(account_id)


@mcp.tool()
def get_my_notice_history(account_id: str, customer_ref: str = "session-user") -> list[dict[str, Any]]:
    """Return notices for one of the customer's accounts."""
    _account(account_id, customer_ref)
    return _bank.get_notice_history(account_id)


@mcp.tool()
def calculate_interest(
    principal: int,
    annual_rate: float,
    days: int,
    tax_rate: float = 0.154,
) -> dict[str, int | float]:
    """Calculate gross interest, tax, and net interest without making a decision."""
    if principal < 0 or days < 0 or annual_rate < 0 or tax_rate < 0:
        raise ValueError("calculation inputs must be non-negative")
    gross = (Decimal(principal) * Decimal(str(annual_rate)) * Decimal(days) / Decimal(365)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    tax = (gross * Decimal(str(tax_rate))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {"principal": principal, "gross_interest": int(gross), "tax": int(tax), "net_interest": int(gross - tax)}


TOOL_FUNCTIONS = {
    "get_my_profile": get_my_profile,
    "get_my_products": get_my_products,
    "get_my_deposits": get_my_deposits,
    "get_my_savings": get_my_savings,
    "get_my_loans": get_my_loans,
    "get_my_transactions": get_my_transactions,
    "get_my_repayments": get_my_repayments,
    "get_my_rate_history": get_my_rate_history,
    "get_my_notice_history": get_my_notice_history,
    "calculate_interest": calculate_interest,
}


def call_finance_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call a registered Finance MCP tool in the local adapter mode."""
    try:
        tool = TOOL_FUNCTIONS[name]
    except KeyError as exc:
        raise ValueError(f"unknown finance tool: {name}") from exc
    return tool(**(arguments or {}))


if __name__ == "__main__":
    mcp.run(transport="stdio")
