"""RAG 검색(법령/상품/사례) Recall@k 평가.

정답 라벨은 사람이 지어낸 문서가 아니라 corpus에 실제로 존재하는 doc_id다 -
각 질의는 특정 문서를 가리키도록 자연어로 새로 작성했고(문서 제목을 그대로
베끼지 않음), 정답은 "이 질의로는 반드시 이 실제 문서가 나와야 한다"는
검증 가능한 사실이다. 상품 라우팅 정확도는 evaluate_aihub.py에서 이미
따로 측정하므로, 여기서는 product 필터 없이 순수 검색 랭킹 품질만 본다.

실행:
    python -m server.tests.evaluate_retrieval
    python -m server.tests.evaluate_retrieval --hybrid
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from server.rag.embeddings import embed_query
from server.rag.retrieval import SearchIndex

# (질의, 정답 doc_id, 근거 설명) - doc_id는 아래 스크립트로 재확인 가능:
#   SearchIndex.from_data_dir(...).chunks 중 path에 해당 파일명이 들어간 chunk.doc_id
CASES = [
    ("임대인이 임차인에게 갱신 거절 통지를 했는지 여부를 다룬 판례를 찾고 싶어요", "99dd4fa31af5"),
    ("회사 이사가 퇴임한 뒤에도 재직 중 보증한 채무의 책임을 계속 져야 하는지 판례가 있나요", "e0420f4d6ed2"),
    ("ETF 목표수익률 특약을 안 지켜서 손실을 봤는데 보상받은 사례가 있나요", "20003891a947"),
    ("폐쇄형 펀드 만기가 지났는데 정산을 안 해줘요, 비슷한 사례 있나요", "e4b69c42cdef"),
    ("전세자금대출 갱신할 때 우대금리 조건이 달라졌다는 안내를 못 받았어요", "2c8f0f0e3ab8"),
    ("생활비로 써야 하는 예금까지 압류당했어요, 해제할 수 있나요", "c6e4a361cbd0"),
    ("대환대출 신청했는데 은행 직원 실수로 계속 지연되고 있어요", "08453d3e941a"),
    ("펀드 가입할 때 중요한 내용을 제대로 설명 안 해줬어요", "314a1d7b5523"),
    ("중고차 담보로 대출받았는데 차 값보다 대출금이 너무 많이 나온 것 같아요", "e816b5f7a15c"),
    ("모임 대표가 대출 연체했다고 모임통장에서 마음대로 돈을 가져갔어요", "11d309abe951"),
    ("대출 만기 연장했더니 금리가 갑자기 너무 많이 올랐어요", "01c1817ae095"),
    ("아파트 중도금대출 금리가 계약할 때보다 너무 많이 올랐어요", "9a8f26f047cb"),
    ("펀드 손실 배상 합의했는데 나중에 돈을 더 달라고 할 수 있나요", "6588bc317482"),
    ("은행에서 가입한 신탁 상품이 원금 보장이 안 된다는 설명을 못 들었어요", "eac5134448e8"),
    ("근저당 설정 이후에 실행된 대출도 담보 범위에 포함되나요", "c5e8ddbe5d0a"),
    ("신용상태가 좋아져서 금리인하를 요구했는데 은행이 거절했어요", "4fd0eb229fd8"),
]

PRODUCTS = [
    ("예금거래기본약관에서 예금주는 어떻게 정의되나요", "41b2b8383a71"),
    ("KB국민행복적금 특약 내용이 궁금해요", "f1eab7b0f8c4"),
    ("KB 생계비계좌는 어떤 조건으로 거래되나요", "0776582200e2"),
    ("KB 주거행복 월세통장 상품 내용을 알고 싶어요", "ba70f17bcfbb"),
    ("국민ONE통장 상품설명서를 보고 싶어요", "d0e5fe3d8503"),
    ("KB 외화MMDA 상품설명서 내용이 궁금해요", "abf899cefb22"),
    ("쓱KB쇼핑적금 특징이 뭔가요", "a2f7e3de4796"),
    ("행복지킴이통장 설명서를 보고 싶어요", "8f4d21a840db"),
    ("KB군인연금평생안심통장이 어떤 상품인가요", "64928e2eb9e4"),
    ("KB하도급지킴이통장 상품설명서 보여주세요", "8298ec80e297"),
    ("KB 스타적금3 상품 특징이 뭔가요", "49c950a0ea1a"),
    ("KB맑은하늘적금 특약 내용을 알고 싶어요", "4db2faf77e2a"),
    ("KB종합통장상품설명서를 보고 싶어요", "91e3d214cfb3"),
    ("KB 지수연계증권92 ELS 투자설명서 내용이 궁금해요", "3403915073db"),
    ("KB미소드림적금은 어떤 상품인가요", "5c2e75d5de0e"),
    ("쓱머니KB통장 상품설명서 내용이 궁금해요", "e0739f1df510"),
    ("내집마련 디딤돌 대출 상품설명서를 보고 싶어요", "b72d35f3d616"),
    ("대출거래약정서 가계용 내용을 확인하고 싶어요", "0b0fec36b804"),
    ("KB스타 신용대출과 KB 비상금대출 차이가 궁금해요", "e1a15d4d81a5"),
    ("KB 매직카대출 중고차 신차 조건이 어떻게 다른가요", "8d5553fd7b35"),
]


GUIDES = [
    ("KB국민은행 불만사항은 어디에서 접수하나요?", "453c50e7e3e4"),
    ("분쟁성 민원은 접수 후 며칠 안에 처리결과를 회신하나요?", "453c50e7e3e4"),
    ("KB국민은행 인터넷뱅킹 고객이 아닌 사람도 민원을 접수할 수 있나요?", "453c50e7e3e4"),
    ("전자민원 내용은 몇 글자까지 입력할 수 있나요?", "453c50e7e3e4"),
    ("칭찬의견은 KB국민은행 홈페이지에서 어떻게 접수하나요?", "453c50e7e3e4"),
    ("분쟁성 민원에는 어떤 유형이 포함되나요?", "453c50e7e3e4"),
]


CANONICAL_DOC_IDS = {
    "41b2b8383a71": {
        "41b2b8383a71",
        "4e8137fa6fa6",
        "c96654dd4ae6",
        "f881da33b78f",
    },
}


def acceptable_doc_ids(expected_doc_id: str) -> set[str]:
    return CANONICAL_DOC_IDS.get(expected_doc_id, {expected_doc_id})


def evaluate(index: SearchIndex, items: list[tuple[str, str]], *, use_hybrid: bool, top_k: int = 5) -> dict[str, object]:
    hits = 0
    misses: list[tuple[str, str]] = []
    for query, expected_doc_id in items:
        vector = embed_query(query) if use_hybrid else None
        results = index.search(query, as_of=date.today(), top_k=top_k, query_embedding=vector)
        found = any(r.doc_id in acceptable_doc_ids(expected_doc_id) for r in results)
        hits += found
        if not found:
            misses.append((query, expected_doc_id))
    return {"n": len(items), "hits": hits, "recall": hits / len(items) if items else 0.0, "misses": misses}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hybrid", action="store_true", help="use embedding-based hybrid search")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    index = SearchIndex.from_data_dir(
        Path("data"), chunks_path=Path("data/corpus/all.jsonl"), exclude_doc_types=frozenset({"glossary"})
    )
    print(f"mode: {'hybrid' if args.hybrid else 'text-only'}, top_k={args.top_k}")
    for label, items in (("cases", CASES), ("products", PRODUCTS), ("guides", GUIDES)):
        result = evaluate(index, items, use_hybrid=args.hybrid, top_k=args.top_k)
        print(f"\n[{label}] recall@{args.top_k}: {result['hits']}/{result['n']} = {result['recall']:.1%}")
        for query, expected in result["misses"]:
            print(f"  놓침: {query[:50]!r} (정답 doc_id={expected})")

    all_items = CASES + PRODUCTS + GUIDES
    total = evaluate(index, all_items, use_hybrid=args.hybrid, top_k=args.top_k)
    print(f"\n[전체] recall@{args.top_k}: {total['hits']}/{total['n']} = {total['recall']:.1%}")


if __name__ == "__main__":
    main()
