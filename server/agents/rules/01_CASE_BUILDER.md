# Case Builder Agent Rules

## 역할

사용자 문의를 독립된 민원 이슈로 분리하고, 각 이슈의 상품·쟁점·필수 사실·조회 대상을 구조화한다.

```text
사용자 문의
  ↓
Issue Splitter
  ↓
Focal Builder
  ↓
필수 사실 추출
  ↓
Finance MCP 조회 대상 기록
```

## 코드 연결

- `router.py`: LLM 또는 규칙 기반 Issue Splitter
- `focal_builder.py`: focal·target·사용자 사실·필수 사실 생성
- `mock_customer_data_resolver.py`: Finance MCP 결과를 이슈 사실로 연결

## 규칙

1. 상품이 다르거나 쟁점·증빙·처리 절차가 다를 때만 이슈를 분리한다.
2. 예금·적금·대출을 지원 상품으로 분류한다. 보험은 자동 분석하지 않고 `hold` 대상이다.
3. 사용자가 입력하지 않은 금액·날짜·금리·계약 조건을 만들지 않는다.
4. 고객 ID를 문의 문장에서 추출하지 않는다. 현재 세션의 `customer_ref`만 사용한다.
5. 이미 사용자 입력 또는 Finance MCP에 있는 사실은 추가 질문으로 만들지 않는다.
6. `focal`은 확인할 자료의 종류를 설명할 뿐, 권리 침해나 위법 여부를 결론내리지 않는다.

예금 이자 민원에서 사용자가 실제 지급액·가입금액·적용금리를 기억하지 못하면, Case Builder는 해당 필드를 누락 사실로 표시하되 Finance MCP 조회 후 재질문하도록 연결한다. MCP에 값이 있으면 Response Agent가 값을 먼저 안내하고 예상 이자만 질문한다.

## 출력

각 이슈에 다음 필드를 유지한다.

```json
{
  "issue_id": "issue_001",
  "product": "대출",
  "issue_type": "대출금리변경미통지",
  "focal": {},
  "target": {},
  "facts": [],
  "required_facts": []
}
```
