from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors

from server.rag.embeddings import embed_query, embed_texts


class _Models:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.calls: list[list[str]] = []

    def embed_content(self, **kwargs: object) -> SimpleNamespace:
        contents = list(kwargs["contents"])
        self.calls.append(contents)
        if len(self.calls) <= self.fail_times:
            raise errors.ServerError(503, {"error": {"message": "overloaded"}}, response=None)
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[float(len(text))] * 3) for text in contents]
        )


class _Client:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.models = _Models(fail_times=fail_times)


class EmbedTextsTests(unittest.TestCase):
    def test_returns_a_vector_per_text(self) -> None:
        client = _Client()
        result = embed_texts(["abc", "de"], task_type="RETRIEVAL_DOCUMENT", client=client)
        self.assertEqual(result, [[3.0, 3.0, 3.0], [2.0, 2.0, 2.0]])
        self.assertEqual(len(client.models.calls), 1)

    def test_empty_input_short_circuits(self) -> None:
        client = _Client()
        self.assertEqual(embed_texts([], task_type="RETRIEVAL_DOCUMENT", client=client), [])
        self.assertEqual(client.models.calls, [])

    @patch("server.rag.embeddings.time.sleep")
    def test_retries_transient_errors_then_succeeds(self, mock_sleep: object) -> None:
        client = _Client(fail_times=2)
        result = embed_texts(["abc"], task_type="RETRIEVAL_DOCUMENT", client=client)
        self.assertEqual(result, [[3.0, 3.0, 3.0]])
        self.assertEqual(len(client.models.calls), 3)

    @patch("server.rag.embeddings.time.sleep")
    def test_gives_up_after_max_retries_without_raising(self, mock_sleep: object) -> None:
        client = _Client(fail_times=99)
        result = embed_texts(["abc", "de"], task_type="RETRIEVAL_DOCUMENT", client=client)
        self.assertEqual(result, [None, None])
        self.assertEqual(len(client.models.calls), 3)


class EmbedQueryTests(unittest.TestCase):
    def test_masks_direct_identifiers_before_sending(self) -> None:
        client = _Client()
        embed_query("계좌 123-456-789012 예금 이자가 이상해요", client=client)
        sent_text = client.models.calls[0][0]
        self.assertNotIn("123-456-789012", sent_text)
        self.assertIn("[계좌번호]", sent_text)

    def test_blank_input_returns_none_without_calling_the_client(self) -> None:
        client = _Client()
        self.assertIsNone(embed_query("   ", client=client))
        self.assertEqual(client.models.calls, [])


if __name__ == "__main__":
    unittest.main()
