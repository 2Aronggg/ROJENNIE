import unittest

from server.agents.facts import resolve_facts
from server.schemas import Fact


def _fact(field: str, value: object) -> Fact:
    return Fact(field=field, value=value, source_ref="user_input", confidence=0.75)


class ResolveFactsConflictTest(unittest.TestCase):
    def test_multiple_scanned_amounts_are_not_a_conflict(self) -> None:
        resolution = resolve_facts([_fact("amount", "30만원"), _fact("amount", "279,180원")])
        self.assertEqual(resolution.conflicts, {})

    def test_semantic_field_mismatch_is_a_conflict(self) -> None:
        resolution = resolve_facts(
            [_fact("실제 적용 금리", "3.3%"), _fact("실제 적용 금리", "3.5%")]
        )
        self.assertIn("실제 적용 금리", resolution.conflicts)

    def test_conflicts_record_provenance_for_audit_trails(self) -> None:
        resolution = resolve_facts(
            [
                Fact(field="product_name", value="예금", source_ref="user_input", confidence=0.9),
                Fact(field="product_name", value="적금", source_ref="mock_data", confidence=0.8),
            ]
        )

        self.assertIn("product_name", resolution.provenance)
        self.assertEqual(resolution.conflicts["product_name"], ["\"예금\"", "\"적금\""])
        self.assertEqual(resolution.provenance["product_name"][0].status, "conflict")
        self.assertEqual(resolution.provenance["product_name"][0].source_type, "USER_STATED")


if __name__ == "__main__":
    unittest.main()
