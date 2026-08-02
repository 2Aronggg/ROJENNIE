from __future__ import annotations

import unittest
from datetime import date

from server.rag.morphology import extract_stems
from server.rag.retrieval import SearchIndex
from server.schemas import DocumentChunk


class ExtractStemsTests(unittest.TestCase):
    def test_conjugated_and_bound_noun_forms_share_a_stem(self) -> None:
        # "연장했더니"(용언 활용)와 "연장시"(의존명사 결합)는 정규식 토크나이저
        # 기준으로는 완전히 다른 토큰이지만, 실제로는 같은 사건을 가리킨다.
        extended_verb = set(extract_stems("대출 만기 연장했더니 금리가 올랐어요"))
        extended_noun = set(extract_stems("대출 연장시 금리를 부당하게 인상"))
        self.assertIn("연장", extended_verb)
        self.assertIn("연장", extended_noun)
        self.assertIn("금리", extended_verb)
        self.assertIn("금리", extended_noun)

    def test_empty_text_returns_empty_list(self) -> None:
        self.assertEqual(extract_stems(""), [])
        self.assertEqual(extract_stems("   "), [])


class StemBackedSearchTests(unittest.TestCase):
    def test_search_matches_via_stem_overlap_despite_zero_raw_token_overlap(self) -> None:
        # ingest 단계에서 공백이 소실된 PDF처럼 극단적인 경우가 아니어도, 조사·
        # 활용형 차이만으로 raw 토큰 오버랩이 0이 될 수 있다는 걸 직접 재현한다.
        chunk = DocumentChunk(
            doc_id="doc1",
            chunk_id="doc1-c1",
            path="local:cases/sample.hwp",
            doc_type="case",
            source="local",
            page=1,
            text="대출 연장시 금리를 부당하게 과다인상 하였는지 여부",
            stems=["대출", "연장", "금리", "부당", "과다", "인상"],
        )
        index = SearchIndex([chunk])

        results = index.search("대출 만기 연장했더니 금리가 갑자기 너무 많이 올랐어요", as_of=date.today(), top_k=5)

        self.assertTrue(results)
        self.assertEqual(results[0].chunk_id, "doc1-c1")


if __name__ == "__main__":
    unittest.main()
