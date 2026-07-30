# Finance MCP·Hybrid Retriever Rules

## 역할

Evidence & Decision Agent가 호출하는 조회 도구의 규칙이다. 내 금융정보는 Finance MCP로 조회하고, 문서 근거는 기존 `retrieval.py` RAG로 검색해 분리한다.

MCP는 데이터를 새로 만들지 않는다.

```text
search_evidence Tool
  → retrieval.py
  → data/ 문서와 인덱스 검색
  → 구조화된 후보 근거 반환
```

## 호출 순서

```text
1. get_my_products
2. 관련 account_id 결정
3. get_my_transactions / get_my_rate_history / get_my_notice_history
4. search_evidence
5. get_evidence
6. Logic Verification
```

고객 ID는 LLM이 만들지 않는다. MCP Server는 세션의 현재 사용자 범위만 조회한다.

## 검색 질의

```text
issue_type + product_type + focal_type + disputed_fact + event_date
```

예시:

```text
maturity_interest_mismatch + deposit
+ contract_and_transaction + expected_vs_actual_interest
+ 2026-08-01
```

## 검색 우선순위

1. 공통 금융 규정
2. 상품 약관·상품설명서
3. 거래·금리·안내 이력과 대조 가능한 근거
4. 공식 분쟁조정·민원 사례
5. 법령·약관·판례는 로컬 RAG 인덱스에서 검색한다. 별도 법령 MCP는 사용하지 않는다.

상품 약관과 공통 규정이 서로 다른 역할을 가지면 하나가 다른 하나를 자동으로 대체하지 않는다. 둘 다 반환하고 Logic Verification에서 적용 범위를 비교한다.

## 반환 형식

```json
{
  "evidence": [
    {
      "evidence_id": "deposit-terms-001-p4",
      "doc_id": "deposit-terms-001",
      "title": "예금거래기본약관",
      "source_type": "terms",
      "page": 4,
      "section": "제9조",
      "effective_from": "2025-01-01",
      "excerpt": "짧은 인용문",
      "relevance_reason": "예금 이자 지급 기준과 관련"
    }
  ],
  "status": "candidate"
}
```

`similarity_score`, `search_method`, 내부 벡터 ID는 사용자에게 반환하지 않는다. 서버 로그와 평가 데이터에만 남길 수 있다.

## 필수 검증

- 문서의 상품 범위가 issue와 맞는지 확인한다.
- 사건일에 문서가 시행 중이었는지 확인한다.
- 자체 제작 민원 JSON·CSV를 법령 근거로 사용하지 않는다.
- 검색 결과가 없으면 `evidence_insufficient`를 반환한다.
- 후보자료만으로 `proceed`를 결정하지 않는다.
- 문서 간 충돌은 Logic Verification으로 전달한다.

## 사용자 표시

검색 후보는 별도 트리 노드가 아니다. 최종 리포트의 `판단 근거`에 묶고, 사용자가 클릭한 경우에만 문서명·페이지·조항·짧은 인용문을 표시한다.
