# Logic Verification Rules

## 역할

Evidence & Decision Agent 안에서 사용자 진술·내 금융정보·계산 결과·MCP RAG 근거를 하나의 사실관계에 적용한다.

Logic Verification은 검색을 새로 만들거나 고객 데이터를 추정하지 않는다. Tool 결과에 있는 사실과 근거만 비교한다.

## 입력

```text
user_statements
my_info_facts
derived_facts
evidence_refs
event_date
```

## 검증 순서

1. 내 금융정보 조회 동의와 계좌·상품 연결을 확인한다.
2. 사용자 진술과 거래·계약 데이터의 값·단위를 비교한다.
3. Calculator Tool의 산식과 입력값을 확인한다.
4. 약관·상품설명서·규정의 적용 상품과 시행일을 확인한다.
5. 조건·예외·안내 의무를 사실 필드와 연결한다.
6. 근거자료가 후보인지 검증 완료인지 구분한다.
7. 충돌·누락·고위험 신호를 Policy Gate에 전달한다.

## 판단 상태

```text
supported   확인된 사실과 근거가 요건에 연결됨
unsupported 확인된 사실이 근거의 요건과 맞지 않음
unknown     핵심 사실 또는 적용 근거가 부족함
conflict    사용자 진술·내 금융정보·문서가 서로 충돌함
```

`unknown`을 임의로 `unsupported`로 바꾸지 않는다. 근거 부족은 위반 확정이 아니다.

## 출력

```json
{
  "finding": "unknown",
  "verified_facts": [
    {
      "field": "actual_interest",
      "value": "279180",
      "source": "my_info",
      "source_ref": "DEP-001:transaction-2026-08-01"
    }
  ],
  "derived_facts": [
    {
      "field": "interest_difference",
      "formula": "300000 - 279180",
      "value": "20820",
      "source": "calculator"
    }
  ],
  "evidence_refs": ["deposit-terms-001-p4"],
  "conditions": [],
  "conflicts": [],
  "recommended_control": "ask"
}
```

계산 결과는 사용자 답변과 구분해 `DERIVED_FACT`로 기록한다.
