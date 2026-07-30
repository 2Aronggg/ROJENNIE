import json
import unittest
from types import SimpleNamespace

from server.agent.rag_query import build_rag_query
from server.schemas import IssueInput


class _Models:
    def generate_content(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            text=json.dumps(
                {"terms": ["만기 이자", "약정이율", "세전 세후", "원천징수", "거래내역"]},
                ensure_ascii=False,
            )
        )


class _Client:
    models = _Models()


class RAGQueryTests(unittest.TestCase):
    def test_llm_terms_are_used_for_retrieval_query(self) -> None:
        issue = IssueInput(
            issue_id="issue_1",
            product="예금",
            issue_type="거래오류",
            text="예금 만기 이자 금액이 예상과 다릅니다.",
        )
        query = build_rag_query(issue, use_llm=True, client=_Client())
        self.assertEqual(query.generated_by, "llm")
        self.assertIn("약정이율", query.text)
        self.assertIn("원천징수", query.text)


if __name__ == "__main__":
    unittest.main()
