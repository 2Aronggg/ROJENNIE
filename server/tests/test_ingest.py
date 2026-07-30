from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from server.rag.ingest import _api_effective_to_by_path, _clean_text, _validity_period


class IngestDateTests(unittest.TestCase):
    def test_effective_to_is_day_before_next_law_version(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "law_20240101.json", root / "law_20250101.json"]
            for path, effective_from in zip(paths, ("20240101", "20250101")):
                path.write_text(
                    json.dumps({"법령": {"기본정보": {"법령ID": "LAW-1", "시행일자": effective_from}}}),
                    encoding="utf-8",
                )

            effective_to = _api_effective_to_by_path(paths)

        self.assertEqual(effective_to[paths[0]], date(2024, 12, 31))
        self.assertIsNone(effective_to[paths[1]])

    def test_product_validity_period_accepts_trailing_dot(self) -> None:
        effective_from, effective_to = _validity_period(
            "준법감시인 심의필 (유효기간: 2026.01.01.~2027.12.31)"
        )
        self.assertEqual(effective_from, date(2026, 1, 1))
        self.assertEqual(effective_to, date(2027, 12, 31))

    def test_pdf_control_characters_are_removed(self) -> None:
        self.assertEqual(_clean_text("금리\x00 3.3%\n"), "금리 3.3%")


if __name__ == "__main__":
    unittest.main()
