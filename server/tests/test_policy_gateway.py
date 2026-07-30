from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from server.policy.gateway import LLMPolicyGateway, PolicyDenied, redact_pii


class _Models:
    def __init__(self) -> None:
        self.contents = ""

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.contents = str(kwargs["contents"])
        return SimpleNamespace(text=json.dumps({"ok": True}))


class _Client:
    def __init__(self) -> None:
        self.models = _Models()


class PolicyGatewayTests(unittest.TestCase):
    def test_masks_identifiers_but_keeps_financial_facts(self) -> None:
        text, count = redact_pii(
            "계좌 123-456-789012, 전화 010-1234-5678, 원금 10000000원"
        )
        self.assertEqual(count, 2)
        self.assertIn("[계좌번호]", text)
        self.assertIn("[전화번호]", text)
        self.assertIn("10000000원", text)

    def test_gateway_masks_input_and_validates_json(self) -> None:
        client = _Client()
        response = LLMPolicyGateway(client=client).generate_json(
            stage="report_composer",
            contents="계좌 123-456-789012의 이자 279180원",
            response_schema={"type": "object"},
        )
        self.assertEqual(json.loads(response.text), {"ok": True})
        self.assertIn("[계좌번호]", client.models.contents)
        self.assertNotIn("123-456-789012", client.models.contents)

    def test_unsupported_stage_is_denied_before_provider_call(self) -> None:
        client = _Client()
        with self.assertRaises(PolicyDenied):
            LLMPolicyGateway(client=client).generate_json(
                stage="unknown",
                contents="test",
                response_schema={},
            )
        self.assertEqual(client.models.contents, "")
