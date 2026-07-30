# KB Key Buddy

금융 소비자의 복합 민원을 이해하고, 사용자의 **내 금융정보**, 약관·상품설명서·사례 RAG, Finance MCP를 함께 확인해 처리 결과와 후속 절차를 안내하는 금융 소비자 보호 에이전트입니다.

현재 MVP는 예금·적금·대출을 지원하며, 실제 은행 내부 시스템 대신 로컬 Mock Bank와 Finance MCP를 사용합니다.

현재 코드 기준 아키텍처는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 구현 과정과 시행착오는 [docs/IMPLEMENTATION_HISTORY.md](docs/IMPLEMENTATION_HISTORY.md)를 참고하세요.

### 저장소 구성

- `server/finance/mock_bank.sqlite3`: 데모용 가상 고객·계약·거래·상환·금리·안내 이력을 저장하는 로컬 SQLite 파일입니다.
- 위 데이터는 실제 고객이나 실제 은행 내부 데이터가 아니며, 현재 가상 고객 `CUST-001`에 연결됩니다.
- `Finance MCP`는 이 SQLite를 직접 노출하지 않고 읽기 전용 금융 Tool로 감쌉니다.
- 로컬 단일 프로세스 데모라면 SQLite로 충분하지만, 실제 배포를 전제로 하면 `Supabase` 연결이 필요합니다. 다중 사용자 로그인, 서버 재시작 후 민원·검토·감사 로그 보존, 여러 인스턴스 간 공유를 담당하게 합니다.
- 첫 단계에서는 민원·리포트·검토·감사 로그와 사용자 정보만 Supabase로 옮기고, 가상 금융 원장과 RAG 원천 문서·corpus는 기존 저장 방식을 유지할 수 있습니다.
- Supabase로 이전하더라도 RAG 원천 문서·corpus는 별도 관리하고, 에이전트가 사용하는 Finance MCP Tool 계약은 유지합니다.

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
FastAPI 오케스트레이터
        ↓
Finance MCP Server
 ├─ 내 금융정보 조회
 ├─ 거래·금리·안내 이력 조회
 ├─ 대출·상환 정보 조회
 └─ 이자 계산
        ↓
Evidence & Decision Agent
 ├─ 사용자 진술·내 금융정보 대조
 ├─ RAG 후보 관련성 검증
 ├─ 시점 기반 규정·약관 RAG
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

- 금융 규정·약관·상품설명서·판례: `data/`의 RAG 원천 문서
- 민원 JSON·CSV: Issue Splitter 평가와 회귀 테스트용
- 가상 고객·계약·거래: 서버 Mock 데이터
- 대출 계약·상환·금리·안내 이력: 서버 Mock 데이터와 Finance MCP

## 디렉터리

```text
client/             React Flow 화면과 API 연동
server/             FastAPI, 파이프라인, Mock 데이터, MCP 연결
server/agents/       Case Builder·RAG·검증·결정·응답 모듈
server/policy/       LLM 호출 정책 게이트
server/mcp/finance/  읽기 전용 금융 Tool 서버·클라이언트
data/               RAG 원천 문서와 평가 데이터
docs/               PRD·현재 아키텍처·구현 이력
```

## 실행

서버 실행은 [server/README.md](server/README.md), 클라이언트 실행은 [client/README.md](client/README.md)를 참고합니다.

## 주의

이 서비스는 금융회사나 금융감독기관의 최종 판단, 법률 자문, 민원 자동 접수를 대신하지 않습니다. 외부 제출·계약 변경·계좌 변경은 수행하지 않으며, 최종 판단은 정식 금융 민원 절차를 통해 확인해야 합니다.
