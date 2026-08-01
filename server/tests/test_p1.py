from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from server import app as app_module
from server.rag.retrieval import SearchIndex, changed_documents, document_manifest
from server.schemas import DocumentChunk


DEPOSIT = "\uc608\uae08"


def _chunk(**overrides) -> DocumentChunk:
    values = {
        "doc_id": "doc1",
        "chunk_id": "chunk1",
        "path": "data/rule.pdf",
        "doc_type": "law",
        "product": [DEPOSIT],
        "source": "test",
        "page": 1,
        "section": "section",
        "text": "alpha deposit rule",
        "effective_from": date(2026, 1, 1),
        "effective_to": date(2026, 12, 31),
        "embedding": [1.0, 0.0],
    }
    values.update(overrides)
    return DocumentChunk(**values)


class RetrievalP1Tests(unittest.TestCase):
    def test_search_combines_text_and_vector_and_respects_effective_dates(self) -> None:
        index = SearchIndex([_chunk()])
        results = index.search(
            "alpha",
            product=DEPOSIT,
            as_of=date(2026, 2, 1),
            query_embedding=[1.0, 0.0],
        )
        self.assertEqual(results[0].match_type, "hybrid")
        self.assertEqual(index.search("alpha", as_of=date(2025, 12, 31)), [])
        self.assertEqual(index.search("alpha", as_of=date(2027, 1, 1)), [])

    def test_document_manifest_reports_changed_files(self) -> None:
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            pdf = data_dir / "rule.pdf"
            pdf.write_bytes(b"one")
            before = document_manifest(data_dir)
            pdf.write_bytes(b"two bytes changed")
            after = document_manifest(data_dir)
            self.assertEqual(changed_documents(after, before), ["rule.pdf"])


class ReviewApiP1Tests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._INDEX = SearchIndex([_chunk()])
        app_module.CASE_STORE.clear()
        app_module.REVIEW_STORE.clear()
        app_module.AUDIT_LOG.clear()
        self.client = TestClient(app_module.app)

    def tearDown(self) -> None:
        app_module._INDEX = SearchIndex([])
        app_module.CASE_STORE.clear()
        app_module.REVIEW_STORE.clear()
        app_module.AUDIT_LOG.clear()

    def test_analyze_builds_graph_and_review_updates_audit(self) -> None:
        payload = {
            "case_id": "case_review",
            "prompt": "alpha",
            "issues": [
                {
                    "issue_id": "issue_1",
                    "product": DEPOSIT,
                    "issue_type": "rule",
                    "text": "alpha",
                }
            ],
        }
        analyzed = self.client.post("/api/v1/cases/analyze", json=payload)
        self.assertEqual(analyzed.status_code, 200)
        self.assertGreaterEqual(len(analyzed.json()["logic_graph"]["nodes"]), 4)

        reviewed = self.client.post(
            "/api/v1/cases/case_review/review",
            json={
                "reviewer_id": "reviewer_1",
                "issue_decisions": {
                    "issue_1": {"control": "hold", "risk_flags": ["manual_review"]}
                },
                "note": "manual check",
            },
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["analysis"]["issues"][0]["decision"]["control"], "hold")
        self.assertEqual(reviewed.json()["analysis"]["issues"][0]["report"]["current_decision"], "\uac80\ud1a0 \ub300\uae30")

        audit = self.client.get("/api/v1/cases/case_review/audit")
        self.assertEqual(audit.status_code, 200)
        event_types = [event["event_type"] for event in audit.json()]
        # 신규 audit logging: issue_validation, decision_gate 추가
        self.assertIn("case.analyzed", event_types)
        self.assertIn("human_review.applied", event_types)


if __name__ == "__main__":
    unittest.main()
