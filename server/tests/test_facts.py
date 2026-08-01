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


if __name__ == "__main__":
    unittest.main()
