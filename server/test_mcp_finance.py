from __future__ import annotations

import unittest

from server.mcp_client import FinanceMCPClient


class FinanceMCPTests(unittest.TestCase):
    def test_inprocess_finance_tools_are_read_only_and_session_scoped(self) -> None:
        client = FinanceMCPClient(transport="inprocess")
        profile = client.call_tool("get_my_profile")
        self.assertEqual(profile["customer_id"], "CUST-001")
        products = client.call_tool("get_my_products")
        self.assertEqual(products["deposits"][0]["account_id"], "DEP-001")
        transactions = client.call_tool("get_my_transactions", {"account_id": "DEP-001"})
        self.assertEqual(transactions[0]["amount"], 279180)
        self.assertEqual(client.call_tool("calculate_interest", {"principal": 20_000_000, "annual_rate": 0.012, "days": 365})["gross_interest"], 240000)

    def test_stdio_finance_tool_round_trip(self) -> None:
        client = FinanceMCPClient(transport="stdio")
        profile = client.call_tool("get_my_profile")
        self.assertEqual(profile["customer_id"], "CUST-001")


if __name__ == "__main__":
    unittest.main()
