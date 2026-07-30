from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).with_name("mock_bank.sqlite3")


CUSTOMER = {
    "customer_id": "CUST-001",
    "name": "김민지",
    "authenticated": True,
    "consent_status": "granted",
}

DEPOSIT = {
    "account_id": "DEP-001",
    "customer_id": "CUST-001",
    "product_type": "deposit",
    "product_name": "KB Star 정기예금",
    "opened_at": "2025-08-01",
    "maturity_at": "2026-08-01",
    "principal": 10_000_000,
    "base_rate": 0.031,
    "preferential_rate": 0.002,
    "applied_rate": 0.033,
    "gross_interest": 330_000,
    "tax": 50_820,
    "net_interest": 279_180,
    "status": "matured",
}

SAVINGS = {
    "account_id": "SAV-001",
    "customer_id": "CUST-001",
    "product_type": "installment_savings",
    "product_name": "KB 내맘대로 적금",
    "opened_at": "2025-09-10",
    "maturity_at": "2026-09-10",
    "base_rate": 0.035,
    "preferential_rate": 0.005,
    "applied_rate": 0.035,
    "preferential_conditions": [
        {
            "condition": "monthly_auto_transfer",
            "status": "failed",
            "failed_at": "2026-06-10",
        }
    ],
    "status": "active",
}

LOAN = {
    "account_id": "LOAN-001",
    "customer_id": "CUST-001",
    "product_type": "loan",
    "product_name": "KB 직장인든든 신용대출",
    "opened_at": "2025-03-15",
    "maturity_at": "2030-03-15",
    "principal": 30_000_000,
    "outstanding_balance": 24_180_000,
    "base_rate": 0.052,
    "preferential_rate": 0.003,
    "applied_rate": 0.049,
    "rate_type": "variable",
    "repayment_method": "원리금균등상환",
    "monthly_payment": 565_000,
    "early_repayment_fee_rate": 0.005,
    "delinquency_status": "정상",
    "status": "active",
}

TRANSACTIONS = [
    {
        "transaction_id": "TX-DEP-001",
        "account_id": "DEP-001",
        "occurred_at": "2026-08-01",
        "transaction_type": "maturity_interest",
        "amount": 279_180,
        "description": "예금 만기 이자 지급",
    }
]

LOAN_REPAYMENTS = [
    {
        "transaction_id": "TX-LOAN-001-001",
        "account_id": "LOAN-001",
        "occurred_at": "2026-06-15",
        "transaction_type": "loan_repayment",
        "amount": 565_000,
        "principal_amount": 441_000,
        "interest_amount": 124_000,
        "description": "대출 원리금 정상 납부",
        "status": "paid",
    },
    {
        "transaction_id": "TX-LOAN-001-002",
        "account_id": "LOAN-001",
        "occurred_at": "2026-07-15",
        "transaction_type": "loan_repayment",
        "amount": 565_000,
        "principal_amount": 443_000,
        "interest_amount": 122_000,
        "description": "대출 원리금 정상 납부",
        "status": "paid",
    },
]

LOAN_RATE_HISTORY = [
    {
        "history_id": "RATE-LOAN-001-001",
        "account_id": "LOAN-001",
        "changed_at": "2026-01-15",
        "previous_rate": 0.047,
        "applied_rate": 0.049,
        "reason": "기준금리 반영",
    }
]

LOAN_NOTICE_HISTORY: list[dict[str, Any]] = []


class MockBankClient:
    """SQLite-backed stand-in for a bank's internal read APIs."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    product_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rate_history (
                    history_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notice_history (
                    notice_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO customers(customer_id, payload) VALUES (?, ?)",
                (CUSTOMER["customer_id"], _dump(CUSTOMER)),
            )
            for account in (DEPOSIT, SAVINGS, LOAN):
                connection.execute(
                    "INSERT OR IGNORE INTO accounts(account_id, customer_id, product_type, payload) VALUES (?, ?, ?, ?)",
                    (
                        account["account_id"],
                        account["customer_id"],
                        account["product_type"],
                        _dump(account),
                    ),
                )
            for transaction in (*TRANSACTIONS, *LOAN_REPAYMENTS):
                connection.execute(
                    "INSERT OR IGNORE INTO transactions(transaction_id, account_id, payload) VALUES (?, ?, ?)",
                    (transaction["transaction_id"], transaction["account_id"], _dump(transaction)),
                )

            for history in LOAN_RATE_HISTORY:
                connection.execute(
                    "INSERT OR IGNORE INTO rate_history(history_id, account_id, payload) VALUES (?, ?, ?)",
                    (history["history_id"], history["account_id"], _dump(history)),
                )
            for notice in LOAN_NOTICE_HISTORY:
                connection.execute(
                    "INSERT OR IGNORE INTO notice_history(notice_id, account_id, payload) VALUES (?, ?, ?)",
                    (notice["notice_id"], notice["account_id"], _dump(notice)),
                )

            connection.commit()

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM customers WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
        return _load(row["payload"]) if row else None

    def get_products(self, customer_id: str) -> dict[str, list[dict[str, Any]]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT account_id, product_type, payload FROM accounts WHERE customer_id = ? ORDER BY account_id",
                (customer_id,),
            ).fetchall()
        products = {"deposits": [], "savings": [], "loans": []}
        for row in rows:
            item = _load(row["payload"])
            summary = {"account_id": item["account_id"], "product_name": item["product_name"]}
            key = {"deposit": "deposits", "installment_savings": "savings", "loan": "loans"}[row["product_type"]]
            products[key].append(summary)
        return products

    def get_deposits(self, customer_id: str) -> list[dict[str, Any]]:
        return self._get_accounts(customer_id, "deposit")

    def get_savings(self, customer_id: str) -> list[dict[str, Any]]:
        return self._get_accounts(customer_id, "installment_savings")

    def get_loans(self, customer_id: str) -> list[dict[str, Any]]:
        return self._get_accounts(customer_id, "loan")

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM accounts WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        if not row:
            return None
        account = _load(row["payload"])
        account["rate_change_history"] = self.get_rate_history(account_id)
        account["notice_history"] = self.get_notice_history(account_id)
        account["repayments"] = self.get_repayments(account_id)
        return account

    def get_transactions(self, account_id: str) -> list[dict[str, Any]]:
        return self._get_child_rows("transactions", "transaction_id", account_id)

    def get_repayments(self, account_id: str) -> list[dict[str, Any]]:
        return [item for item in self.get_transactions(account_id) if item.get("transaction_type") == "loan_repayment"]

    def get_rate_history(self, account_id: str) -> list[dict[str, Any]]:
        return self._get_child_rows("rate_history", "history_id", account_id)

    def get_notice_history(self, account_id: str) -> list[dict[str, Any]]:
        return self._get_child_rows("notice_history", "notice_id", account_id)

    def _get_accounts(self, customer_id: str, product_type: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM accounts WHERE customer_id = ? AND product_type = ? ORDER BY account_id",
                (customer_id, product_type),
            ).fetchall()
        return [self.get_account(_load(row["payload"])["account_id"]) for row in rows]

    def _get_child_rows(self, table: str, key: str, account_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT payload FROM {table} WHERE account_id = ? ORDER BY {key}",
                (account_id,),
            ).fetchall()
        return [_load(row["payload"]) for row in rows]


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load(value: str) -> dict[str, Any]:
    return json.loads(value)
