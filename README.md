# KB Key Buddy

금융 소비자의 복합 민원을 이해하고, 사용자의 **내 금융정보**, 약관·상품설명서·사례 RAG, 법령 MCP를 함께 확인해 처리 결과와 후속 절차를 안내하는 금융 소비자 보호 에이전트입니다.

대출은 구현 범위에서 제외합니다. 현재 MVP는 `data/`에 있는 예금·적금·ELS 문서와 가상 금융정보를 대상으로 합니다.

## 핵심 구조

```text
사용자 로그인·내 금융정보 조회 동의
        ↓
사용자 문의 입력
        ↓
Case Builder Agent
 ├─ Issue Splitter
 ├─ Focal Builder
 └─ 필수 사실 추출
        ↓
FastAPI MCP Client
        ↓
Finance MCP Server
 ├─ 내 금융정보 조회
 ├─ 거래·금리·안내 이력 조회
 ├─ RAG 근거 검색
 └─ 이자 계산
        ↓
Evidence & Decision Agent
 ├─ 사용자 진술·내 금융정보 대조
 ├─ RAG 후보 관련성 검증
 ├─ 선택적 법령 MCP 조회
 └─ Logic Verification
        ↓
Deterministic Policy Gate
 ├─ proceed: 판단 가능
 ├─ ask: 핵심 정보 추가 확인
 ├─ amend: 입력·증빙 보완
 └─ hold: 고위험·전문가 검토
        ↓
Response Agent
 ├─ 민원내용
 ├─ 처리결과
 ├─ 소비자 유의사항
 └─ 제출 서류·후속 절차
```

MCP는 새 에이전트가 아닙니다. 기존 조회·검색·계산 함수를 LLM이 호출할 수 있도록 연결하는 도구 계층입니다. RAG의 원천 문서는 계속 `data/`에 있고, `search_evidence` MCP Tool이 기존 RAG 검색 함수를 호출합니다.

## MCP Tools

초기 Finance MCP는 읽기 전용으로 구성합니다.

```text
get_my_profile()
get_my_products()
get_my_transactions(account_id)
get_my_rate_history(account_id)
get_my_notice_history(account_id)
search_evidence(query, product_type)
get_evidence(evidence_id)
calculate_interest(principal, rate, days, tax_rate)
```

고객 ID는 LLM이나 사용자가 입력하지 않습니다. 로그인 세션의 가상 고객 `CUST-001`을 서버가 연결하고, MCP는 현재 사용자의 `/me` 범위만 조회합니다.

## 리포트 원칙

- 사용자가 이미 입력한 금액·금리·기간은 다시 묻지 않습니다.
- 내 금융정보에 없고 문의에도 없는 핵심 값만 `ask`로 질문합니다.
- RAG 검색 후보는 노드로 분리하지 않고 리포트의 `판단 근거`에 묶습니다.
- 사용자 화면에는 검색 점수·검색 방식·내부 chunk ID를 노출하지 않습니다.
- 근거를 클릭하면 문서명·페이지·조항·짧은 인용문을 상세 표시합니다.
- 최종 리포트는 `민원내용 / 처리결과 / 소비자 유의사항` 형식으로 생성합니다.

## 데이터

- 금융 규정·약관·상품설명서: `data/`의 RAG 원천 문서
- 민원 JSON·CSV: Issue Splitter 평가와 회귀 테스트용
- 가상 고객·계약·거래: 서버 Mock 데이터
- 대출 데이터와 대출 처리 경로: 없음

## 디렉터리

```text
client/             React Flow 화면과 API 연동
server/             FastAPI, 파이프라인, Mock 데이터, MCP 연결
server/agents/       에이전트가 읽는 규칙 문서와 구현 모듈
data/               RAG 원천 문서와 평가 데이터
docs/               PRD와 작업 문서
```

## 실행

서버 실행은 [server/README.md](server/README.md), 클라이언트 실행은 [client/README.md](client/README.md)를 참고합니다.

## 주의

이 서비스는 금융회사나 금융감독기관의 최종 판단, 법률 자문, 민원 자동 접수를 대신하지 않습니다. 외부 제출·계약 변경·계좌 변경은 수행하지 않으며, 최종 판단은 정식 금융 민원 절차를 통해 확인해야 합니다.
