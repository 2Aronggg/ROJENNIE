from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from server.policy.gateway import (
    LLMPolicyGateway,
    PolicyDenied,
    contains_forbidden_claim,
    redact_pii,
    sanitize_llm_text,
    sanitize_llm_texts,
)


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

    def test_sanitize_drops_compensation_and_legal_conclusion_claims(self) -> None:
        self.assertEqual(sanitize_llm_text("배상액 100만원을 지급해야 합니다"), "")
        self.assertEqual(sanitize_llm_text("이것은 명백히 불완전판매입니다"), "")
        self.assertEqual(sanitize_llm_text("환급될 것입니다"), "")
        self.assertEqual(sanitize_llm_text("근거 문서를 확인하세요"), "근거 문서를 확인하세요")

    def test_forbidden_claim_regex_catches_softened_legal_and_amount_estimates(self) -> None:
        self.assertTrue(contains_forbidden_claim("은행의 잘못으로 보입니다."))
        self.assertTrue(contains_forbidden_claim("불완전판매에 해당할 수 있습니다."))
        self.assertTrue(contains_forbidden_claim("약 100만원 환급 예상입니다."))
        self.assertTrue(contains_forbidden_claim("환급 가능성이 높습니다."))
        self.assertFalse(contains_forbidden_claim("확인된 사실과 근거 자료를 함께 검토했습니다."))

    def test_gateway_rejects_forbidden_output_even_when_json_is_valid(self) -> None:
        class _ForbiddenModels(_Models):
            def generate_content(self, **kwargs: object) -> SimpleNamespace:
                self.contents = str(kwargs["contents"])
                return SimpleNamespace(text=json.dumps({"result": "약 100만원 환급 예상입니다."}, ensure_ascii=False))

        client = _Client()
        client.models = _ForbiddenModels()

        with self.assertRaises(ValueError):
            LLMPolicyGateway(client=client).generate_json(
                stage="report_composer",
                contents="근거 자료 기준으로 답변",
                response_schema={"type": "object"},
            )

    def test_sanitize_texts_filters_list_and_keeps_order(self) -> None:
        result = sanitize_llm_texts(["증빙 서류를 준비하세요", "배상액을 요구하세요", "거래일을 확인하세요"])
        self.assertEqual(result, ["증빙 서류를 준비하세요", "거래일을 확인하세요"])
