from datetime import date
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from server import app as app_module
from server.agents.facts import resolve_facts
from server.rag.retrieval import SearchIndex
from server.schemas import DocumentChunk, Fact


class P0Tests(unittest.TestCase):
    def test_fact_conflict_keeps_latest(self) -> None:
        result = resolve_facts(
            [
                Fact(field="실제 지급 금액", value=100, recorded_date=date(2026, 1, 1)),
                Fact(field="실제 지급 금액", value=120, recorded_date=date(2026, 1, 2)),
            ]
        )
        self.assertEqual(result.latest["실제 지급 금액"].value, 120)
        self.assertIn("실제 지급 금액", result.conflicts)

    def test_search_returns_product_evidence(self) -> None:
        index = SearchIndex(
            [
                DocumentChunk(
                    doc_id="doc1",
                    chunk_id="chunk1",
                    path="data/example.pdf",
                    doc_type="terms",
                    product=["예금"],
                    source="test",
                    page=2,
                    text="예금 계약해지 절차와 지급 조건을 안내합니다.",
                )
            ]
        )
        results = index.search("예금 계약해지", product="예금")
        self.assertEqual(results[0].chunk_id, "chunk1")

    def test_api_analyze_and_get(self) -> None:
        app_module._INDEX = SearchIndex([])
        client = TestClient(app_module.app)
        payload = {
            "case_id": "case_test",
            "prompt": "예금 해지가 지연되었습니다.",
            "issues": [
                {
                    "issue_id": "issue_1",
                    "product": "예금",
                    "issue_type": "계약해지_지연",
                    "text": "예금 해지가 지연되었습니다.",
                    "required_facts": ["contract_date"],
                }
            ],
        }
        response = client.post("/api/v1/cases/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["issues"][0]["decision"]["control"], "ask")
        self.assertEqual(client.get("/api/v1/cases/case_test").status_code, 200)


if __name__ == "__main__":
    unittest.main()
