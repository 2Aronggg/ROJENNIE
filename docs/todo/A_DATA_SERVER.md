# A TODO: 데이터·서버·MCP

담당 브랜치: `feat/data-server`

담당 범위는 가상 금융정보, RAG, FastAPI, Finance MCP와 B가 사용할 API·Tool 계약이다. `server/agent/`의 에이전트 프롬프트와 `client/` 화면은 수정하지 않는다.

## P0: 데이터·기존 서버

- [x] PDF 텍스트 추출 및 페이지·조항 단위 chunk 생성
- [x] `doc_id`, `doc_type`, `product`, `issue_types`, `source`, `effective_from` 메타데이터 부여
- [x] 사건일과 규정 시행일 비교
- [x] 공통 case schema와 API Pydantic 모델 정의
- [x] 공통 규정·상품 문서 검색 파이프라인
- [x] 검색 결과에 문서명·페이지·조항 연결
- [x] `single_issue_75.json`, `complex_issue_75.json` 로더
- [x] `ground_truth_subissues` 기반 분해 평가기
- [x] `POST /api/v1/cases/analyze`
- [x] `GET /api/v1/cases/{case_id}`
- [x] 합성 고객·예금·적금 데이터와 Mock 조회 함수
- [ ] 세션 사용자와 `customer_ref` 연결
- [ ] 조회 동의 상태 검증
- [ ] 서버 재시작 후 case 기록을 보존할 SQLite 저장

## P1: Finance MCP

- [x] `server/finance_mcp/finance_server.py` 생성
- [x] `get_my_profile` Tool 구현
- [x] `get_my_products` Tool 구현
- [x] `get_my_deposits`, `get_my_savings`, `get_my_loans` Tool 구현
- [x] `get_my_transactions` Tool 구현
- [x] `get_my_repayments` Tool 구현
- [x] `get_my_rate_history` Tool 구현
- [x] `get_my_notice_history` Tool 구현
- [x] `calculate_interest` 결정적 Tool 구현
- [x] `server/finance_mcp/client.py`에서 Tool 호출 구현
- [x] MCP stdio 왕복 테스트 작성
- [x] MCP Tool이 쓰기 작업을 수행하지 않는지 테스트
- [ ] Tool 결과에 `trace_id`와 `evidence_id` 연결
- [ ] MCP 실패·타임아웃 시 안전한 오류 응답
- [ ] Tool 결과에 `trace_id`와 `evidence_id` 연결
- [ ] MCP 실패·타임아웃 시 안전한 오류 응답
- [ ] MCP Inspector 또는 최소 호출 테스트 작성
- [ ] MCP Tool이 쓰기 작업을 수행하지 않는지 테스트

## P1: 검색·근거 계약

- [x] Vector Search와 Full-Text Search 결합
- [x] 사건 그래프에 날짜·금액·문서·답변 관계 저장
- [x] `POST /api/v1/cases/{case_id}/review`
- [x] 로컬 `retrieval.py` 검색 결과 반환 형식 확정
- [ ] 검색 점수·검색 방식·내부 chunk ID를 기본 응답에서 제거
- [ ] 사건일보다 늦게 시행된 문서 차단
- [ ] RAG 후보와 확인된 근거를 구분
- [ ] Logic Verification 이전의 후보자료가 proceed 판단에 사용되지 않도록 가드

## A가 B에게 제공할 계약

- [x] case schema
- [x] API request/response 예시
- [x] `evidence_refs` 형식
- [x] 결정 상태 enum
- [x] 오류·누락 정보 응답 형식
- [ ] `customer_ref`, `consent_status`, `my_info_refs` 필드
- [ ] MCP Tool 입력·출력 JSON schema
- [ ] `mcp_trace` 감사 로그 형식

## 데이터 추가 기준

현재 예금·적금·대출 MVP에 필수 데이터는 더 추가하지 않는다. 다음은 기능 확장 시에만 진행한다.

- [ ] 공식 금융 분쟁조정·민원 사례 원문
- [ ] 공식 민원 절차·제출 서류 정보
- [ ] 첨부 HWP·PDF 추출 테스트 문서
- [ ] 추가 상품 설명서

실제 고객정보와 실제 계좌번호는 수집하지 않는다.

## 검증 명령

```powershell
python -m unittest server.test_p1 server.test_mock_data server.agent.test_focal_builder server.agent.test_rag_query
```
