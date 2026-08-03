import os
import unittest
from datetime import date
from unittest.mock import Mock

from server.rag.pgvector import SupabaseVectorStore


class PgVectorTests(unittest.TestCase):
    def test_disabled_store_does_not_call_supabase(self) -> None:
        os.environ.pop("SUPABASE_RAG_ENABLED", None)
        store = Mock()
        vector = SupabaseVectorStore(store)
        self.assertEqual(vector.search([1.0, 0.0], as_of=date.today()), [])
        store.rpc.assert_not_called()

    def test_maps_rpc_rows_to_evidence(self) -> None:
        os.environ["SUPABASE_RAG_ENABLED"] = "true"
        store = Mock()
        store.base_url = "https://example.supabase.co"
        store.api_key = "secret"
        store.rpc.return_value = [
            {
                "doc_id": "doc-1",
                "chunk_id": "chunk-1",
                "path": "local:products/deposit.pdf",
                "page": 2,
                "section": "제1조",
                "content": "근거 내용",
                "similarity": 0.91,
                "effective_from": "2025-01-01",
                "effective_to": None,
            }
        ]
        result = SupabaseVectorStore(store).search([1.0, 0.0], product="예금")
        self.assertEqual(result[0].chunk_id, "chunk-1")
        self.assertEqual(result[0].match_type, "vector")
        store.rpc.assert_called_once()
        os.environ.pop("SUPABASE_RAG_ENABLED", None)


if __name__ == "__main__":
    unittest.main()
