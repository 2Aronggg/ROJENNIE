# Issue Splitter Rules

## 역할

Case Builder Agent의 첫 단계다. 한 문장에 섞인 금융 문제를 서로 독립적으로 검토할 민원 Case로 나눈다.

Issue Splitter는 다음을 하지 않는다.

- 내 금융정보 조회
- Finance MCP·RAG 호출
- 위법 여부 판단
- 고객 ID 추측
- 사용자가 이미 제공한 사실 재질문

## 분리 기준

다음 중 하나라도 다르면 별도 issue로 분리한다.

- 금융상품 또는 계좌
- 문제의 원인
- 확인해야 할 focal 자료
- 요구하는 해결 방법
- 적용될 규정·약관

예시:

```text
예금 만기 이자 금액이 예상과 다르고,
적금 금리 변경 안내도 받지 못했습니다.
```

```text
issue_001: 예금 만기 이자 금액 불일치
issue_002: 적금 금리 변경 안내 미수신
```

## 출력

```json
{
  "issue_id": "issue_001",
  "product": "deposit",
  "issue_type": "maturity_interest_mismatch",
  "user_text": "예금 만기 이자 금액이 예상과 다르다",
  "requested_action": "계약조건·거래내역·약관 확인",
  "mentioned_facts": [
    {"field": "expected_interest", "value": "300000", "source": "user"}
  ],
  "unresolved_parts": []
}
```

`mentioned_facts`에는 사용자가 실제 입력한 사실만 넣는다. 금액의 의미가 불명확하면 임의 확정하지 않고 `unresolved_parts`에 기록한다.

## 모호한 금액

사용자가 “2천만 원”이라고 했을 때 가입 원금인지 예상 이자인지 불분명하면 다음 단계에서 재확인한다.

```text
2천만 원은 예금에 가입한 원금인가요,
만기 때 예상한 이자 금액인가요?
```

## 규칙

- 하위 민원마다 고유한 `issue_id`를 부여한다.
- 하나의 issue에 여러 상품을 임의로 넣지 않는다.
- 문의에 명시된 금액·금리·날짜를 누락하지 않는다.
- 예금·적금·대출 issue는 상품별로 분리하고, 보험 issue는 지원 제외로 표시한다.
- 분리가 불명확한 부분만 `ask` 후보로 전달한다.
