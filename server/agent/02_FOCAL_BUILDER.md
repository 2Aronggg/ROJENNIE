# Focal Builder Rules

## 역할

Case Builder Agent의 두 번째 단계다. Issue Splitter가 만든 각 issue에 대해 어떤 자료와 사실을 확인해야 하는지 구조화한다.

Focal Builder는 결론을 내리지 않는다. 내 금융정보 조회와 RAG 검색을 직접 수행하지 않고, 다음 단계가 호출할 Tool의 입력을 만든다.

## 출력

```json
{
  "issue_id": "issue_001",
  "product": "deposit",
  "focal": ["contract", "transaction_statement"],
  "target": "maturity_interest",
  "required_facts": [
    "expected_interest",
    "actual_interest",
    "principal",
    "applied_rate",
    "maturity_date"
  ],
  "known_facts": [],
  "missing_facts": [],
  "retrieval_query": {
    "issue_type": "maturity_interest_mismatch",
    "product_type": "deposit",
    "focal_type": "contract_and_transaction",
    "disputed_fact": "expected_vs_actual_interest"
  }
}
```

## focal 후보

| focal | 사용 시점 |
|---|---|
| `contract` | 가입금액·약정금리·기간·우대조건 확인 |
| `transaction_statement` | 실제 지급액·입출금·만기 거래 확인 |
| `rate_history` | 금리·우대금리 변경 확인 |
| `notice_history` | 변경 안내 발송·수신 여부 확인 |
| `product_manual` | 상품 설명서의 계산·조건 확인 |
| `complaint_record` | 기존 민원·답변 확인 |

## 사실 추출 규칙

- 사용자 입력에 있는 사실은 `known_facts`에 기록한다.
- Finance MCP에서 조회할 사실은 `required_facts`와 `my_info_query`에 기록한다.
- 없는 값을 추정하지 않는다.
- 금액의 단위와 의미를 보존한다.
- `event_date`와 `recorded_date`를 혼동하지 않는다.
- 사용자가 “30만원 예상, 279,180원 입금, 가입금액 1,000만원, 금리 3.3%”라고 입력했다면 이 네 값을 다시 질문하지 않는다.

## MCP 연결용 정보

Focal Builder는 다음 호출을 요청할 수 있다.

```json
{
  "finance_tools": [
    {"name": "get_my_products", "arguments": {}},
    {"name": "get_my_transactions", "arguments": {"account_id": "DEP-001"}}
  ]
}
```

실제 `customer_id`는 이 출력에 넣지 않는다. 서버 세션이 현재 사용자와 연결한다.

## 누락 정보

누락 정보는 검색 전에 목록화한다. 단, Finance MCP에서 확인할 수 있는 정보는 사용자에게 먼저 묻지 않는다.

```text
내 금융정보에 예치기간이 없음
문의에도 예치기간이 없음
→ ask 후보: 예치기간 질문
```

여기까지가 Focal Builder의 결과다. “은행이 규정을 위반했는지”, “환급해야 하는지”는 Evidence & Decision Agent와 Policy Gate에서 판단한다.
