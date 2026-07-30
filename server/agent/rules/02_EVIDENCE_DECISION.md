# Evidence & Decision Agent Rules

## 역할

Case Builder가 만든 각 민원에 대해 Finance MCP의 내 금융정보와 로컬 RAG 후보자료를 함께 확인하고, Logic Verification과 Policy Gate가 판단할 입력을 구성한다.

```text
Case Builder 결과
   ↓
Finance MCP: 내 계약·거래·상환·금리·안내 이력
   ↓
Local RAG: 규정·약관·상품설명서·확보된 사례
   ↓
Logic Verification
   ↓
Policy Gate
```

## 실제 코드 연결

- `server/finance_mcp/client.py`: Finance MCP Tool 호출
- `server/finance_mcp/finance_server.py`: 가상 금융정보를 읽기 전용 Tool로 제공
- `server/retrieval.py`: `data/`의 로컬 문서 검색
- `server/agent/rag_query.py`: LLM 또는 규칙 기반 RAG 검색어 생성
- `server/agent/logic_verification.py`: 사실·계약·거래·근거의 연결 검증

## 조회 순서

1. 현재 세션의 사용자·동의 상태 확인
2. 해당 상품의 계약 데이터 조회
3. 필요한 거래내역·상환내역·금리이력·안내이력 조회
4. 사건일과 규정 시행일을 반영해 규정·상품·사례 corpus를 분리 검색
5. focused query들을 full-text 후보 검색 후 RRF로 재순위화
6. 용어 사전은 설명용으로만 사용하고 판단 근거 후보에서 제외
7. RAG 후보를 Logic Verification으로 전달
8. 후보자료만으로 결론을 확정하지 않고 Policy Gate에 전달

예금 이자 민원에서 조회된 실제 지급액·가입금액·적용금리는 확인된 사실로 보존한다. 사용자가 예상 이자만 모를 때는 이 사실을 먼저 안내하고 예상 이자만 질문한다. MCP에 해당 값이 없을 때만 사용자에게 실제 지급액·가입금액·금리를 질문한다.

Finance MCP는 고객 ID를 문의 문장에서 추출하지 않는다. 현재 세션의 `customer_ref`에 연결된 데이터만 조회한다.

## RAG와 MCP의 경계

- Finance MCP: 사용자별 금융 데이터와 결정적 계산 Tool
- Local RAG: 규정·약관·상품설명서·사례 문서 검색
- Logic Verification: 검색 결과가 실제 사실과 적용 조건에 맞는지 검증
- Policy Gate: `proceed`, `ask`, `amend`, `hold` 결정

RAG 후보자료는 검증 전까지 `RAG_CANDIDATE`다. 후보가 있다는 이유만으로 `proceed`하지 않는다. 검색 점수는 후보 정렬용일 뿐 법적 확정 근거가 아니다.

## 반환에 포함할 것

```json
{
  "my_info_refs": ["DEP-001"],
  "verified_facts": [],
  "evidence_refs": [],
  "missing_facts": [],
  "warnings": []
}
```

사용자 화면에는 내부 MCP 요청 전문, 검색 점수, 내부 토큰·벡터를 노출하지 않는다. 최종 리포트에는 검증에 사용한 문서명·페이지·조항·시행일만 보여준다.
