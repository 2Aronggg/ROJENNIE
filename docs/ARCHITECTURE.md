# KB Key Buddy 현재 아키텍처

문서 기준: 2026-07-31  
이 문서는 PRD가 아니라 현재 코드와 데이터 배치를 기준으로 한 구현 안내서입니다.

## 1. 제품 범위

KB Key Buddy는 금융 앱 안에서 사용자의 금융정보와 민원 내용을 함께 확인하는 금융소비자 보호 기능입니다.

현재 정식 지원 상품:

~~~text
예금 · 적금 · 대출
~~~

라우터는 보험·펀드·ELS·공통 문의도 식별할 수 있지만, 현재 규정·상품·가상 금융 데이터가 준비된 범위는 예금·적금·대출입니다. 데이터가 부족한 상품은 임의로 결론내리지 않고 보완 필요 또는 검토 대기로 보냅니다.

구현하지 않는 범위:

- 실제 은행 내부 시스템 연결
- 실제 계좌 조회·이체·해지·환불·민원 접수
- 대출 승인 또는 고객 신용도 판단
- 금융회사의 법적 책임·배상 여부 확정
- Supabase 영구 저장 연결(서버에서 `SUPABASE_PERSISTENCE=true`일 때 활성화)

## 기술 스택 및 배포 구조

### 기술 스택

| 영역 | 기술 | 역할 |
| --- | --- | --- |
| Client | React 19, Vite, @xyflow/react | 민원 상담·트리·리포트·마이 페이지·관리자 화면 |
| API | FastAPI, Uvicorn, Pydantic | 브라우저 요청 검증과 전체 파이프라인 오케스트레이션 |
| LLM | Gemini API, google-genai | 라우팅·RAG 질의·논리 검증·리포트 초안 |
| LLM 보호 | LLM Policy Gateway | 개인정보 마스킹, 허용 단계 확인, JSON 검증, fallback |
| 금융 Tool | Python MCP SDK, Finance MCP | 현재 사용자 가상 금융정보·계산 조회 |
| RAG | pypdf, JSONL corpus, IDF·RRF 검색 | 규정·약관·상품설명서·사례 검색 |
| 앱 저장소 | Supabase PostgreSQL | 사용자·민원·리포트·검토·감사 로그 영구 저장 |
| 데모 금융 원장 | SQLite Mock Bank | CUST-001의 가상 예금·적금·대출·거래 데이터 |

Supabase에는 1차로 profiles, cases, case_issues, reviews, audit_logs 테이블을 만들었습니다. `server/supabase_store.py`가 REST API로 민원·검토·감사 로그를 저장하고, 서버 재시작 후 개별 민원을 복원합니다. 연결은 `SUPABASE_PERSISTENCE=true`일 때만 켜지며, 기본값은 로컬 데모와 테스트를 위한 메모리 저장입니다.

### Vercel 배포 목표

Vercel을 배포 대상으로 사용합니다. Vercel은 React/Vite 정적 클라이언트와 Python Runtime 기반 FastAPI Function을 함께 지원하므로, 먼저 하나의 저장소에서 다음 구성을 검증합니다. [Vercel FastAPI 공식 문서](https://vercel.com/docs/frameworks/backend/fastapi)

~~~text
사용자 브라우저
        ↓
Vercel
  ├─ React/Vite Client
  └─ FastAPI Python Function
        ├─ Supabase: 민원·리포트·검토·감사 로그
        ├─ RAG corpus: 읽기 전용 배포 파일
        └─ Finance MCP inprocess: 가상 금융정보 조회
~~~

배포 시 원칙:

- Supabase를 민원·리포트·검토·감사 로그의 영구 저장소로 사용한다.
- SQLite는 쓰기 저장소로 사용하지 않고 가상 금융 원장의 읽기용 데이터로만 유지한다.
- Finance MCP는 서버 내부 inprocess 모드를 사용하고, 별도 stdio 프로세스 의존성을 배포 경로에 넣지 않는다.
- RAG corpus는 배포 번들 크기와 초기화 시간을 확인한 뒤 포함하며, 커지면 Object Storage나 별도 RAG 서버로 분리한다.
- Client 환경변수에는 VITE_API_BASE만 두고, Supabase 서버 키와 Gemini 키는 브라우저에 노출하지 않는다.
- Vercel Function의 번들 크기·실행시간·RAG 응답시간 테스트를 통과하지 못하면 Client는 Vercel에 두고 FastAPI만 별도 서버로 분리한다.

## 2. 전체 흐름

~~~text
사용자 로그인·조회 동의
        ↓
오른쪽 상담창에 민원 입력
        ↓
Case Builder Agent
  ├─ Issue Splitter
  ├─ Focal Builder
  ├─ 필수 사실 추출
  └─ 예금·적금·대출 상품 연결
        ↓
Evidence & Decision Agent
  ├─ Finance MCP 또는 Mock Bank 조회
  ├─ 사용자 진술과 금융정보 대조
  ├─ temporal RAG 검색
  ├─ 근거 후보 관련성 검증
  └─ Logic Verification
        ↓
Deterministic Policy Gate
  ├─ proceed: 판단 가능
  ├─ ask: 핵심 정보 확인 필요
  ├─ amend: 입력·증빙 보완 필요
  └─ hold: 고위험·충돌·상담원 검토
        ↓
Response Agent
  ├─ 민원내용
  ├─ 처리결과
  ├─ 소비자 유의사항
  └─ 제출 서류·후속 절차
        ↓
CaseAnalysis 저장
        ↓
XYFlow 민원 트리·상담창·완료 민원 화면
~~~

브라우저는 MCP를 직접 호출하지 않습니다. FastAPI가 세션 사용자 범위를 확인한 뒤 MCP·Mock Bank·RAG·정책 게이트를 순서대로 오케스트레이션합니다.

## 3. 에이전트와 모듈 경계

Issue Splitter와 Focal Builder는 독립적인 네트워크 에이전트가 아니라 Case Builder 내부 단계입니다. 단계를 잘게 쪼개면 호출과 상태 전달이 늘어나므로 현재는 하나의 Case Builder로 묶었습니다.

| 계층 | 구현 위치 | 책임 |
| --- | --- | --- |
| Case Builder | server/agents/router.py, focal_builder.py, facts.py | 복합 문의를 민원 단위로 나누고 상품·쟁점·focal·필수 사실을 구조화 |
| 금융정보 조회 | server/agents/mock_customer_data_resolver.py, server/mcp/finance/ | 현재 사용자에게 허용된 예금·적금·대출·거래·상환·금리·안내 정보 조회 |
| Evidence & Decision | server/app.py, server/agents/rag_query.py, logic_verification.py | 사실과 문서 근거를 연결하고 시점·상품·조항을 검증 |
| RAG Retriever | server/rag/retrieval.py | 후보 문서 검색, 날짜 필터, 상품 필터, 다중 쿼리 RRF |
| Calculator | server/agents/calculator.py | 이자·차이·세후 금액 등 재현 가능한 산식 계산 |
| Logic Verification | server/agents/logic_verification.py | 요건·예외·증거 상태·문서 충돌을 판단 근거로 정리 |
| Decision Gate | server/agents/decision_gate.py | 결정 상태와 위험도·상담원 검토 여부를 결정하는 비LLM 정책 |
| LLM Policy Gateway | server/policy/gateway.py | LLM 호출 전 개인정보 마스킹, 허용 단계 확인, JSON 검증, 호출 감사 |
| Response Agent | server/agents/report_composer.py, response_composer.py | 근거에 기반해 민원내용·처리결과·유의사항·후속 절차 작성 |

LLM은 검색어·구조화·설명문을 만들 수 있지만 배상·환급·법적 책임, 사기 여부, 대출 승인·신용도, 계좌 실행, 근거 없는 예외를 단독으로 확정하지 않습니다. 결정 상태와 검토 여부는 server/agents/decision_gate.py가 최종 통제합니다.

## 4. LLM Policy Gateway

모든 Gemini 호출은 다음 경로를 통과합니다.

~~~text
에이전트
  ↓
LLMPolicyGateway.generate_json()
  ├─ 허용 stage 확인
  ├─ 빈 입력 거부
  ├─ 주민번호·계좌번호·카드번호·전화번호·이메일 마스킹
  ├─ Gemini 호출
  ├─ 응답 개인정보 재검사
  ├─ JSON 파싱·객체 확인
  └─ 원문 대신 해시와 메타데이터만 감사 로그
~~~

허용 단계는 issue_splitter, rag_query, logic_verification, report_composer입니다. 게이트는 외부 정책 서버가 아니라 FastAPI 내부의 공통 호출 래퍼입니다. Gemini 장애나 503이면 각 단계가 준비한 결정론적 fallback을 사용합니다.

## 5. Finance MCP

Finance MCP는 에이전트가 호출하는 읽기 전용 금융 Tool 계층입니다. server/mcp/finance/finance_server.py가 현재 가상 금융 API 역할을 합니다.

~~~text
FinanceMCPClient
  ├─ inprocess: 같은 프로세스의 Finance MCP 호출
  └─ stdio: 별도 MCP 서버 프로세스 호출
~~~

주요 Tool:

~~~text
get_my_profile
get_my_products
get_my_deposits
get_my_savings
get_my_loans
get_my_transactions
get_my_repayments
get_my_rate_history
get_my_notice_history
calculate_interest
~~~

고객 ID는 LLM이나 사용자가 직접 지정하지 않습니다. 세션 session-user를 서버가 가상 고객 CUST-001에 연결하고, Tool은 해당 고객 소유 계좌만 반환합니다. 쓰기 Tool과 실제 은행 연동은 아직 없습니다.

## 6. 가상 금융 데이터

현재 데이터베이스는 Supabase가 아니라 server/finance/mock_bank.sqlite3입니다. server/finance/mock_data.py가 초기 데이터를 만들고 조회 계층은 고객 범위 검사를 적용합니다.

~~~text
CUST-001
  ├─ DEP-001 예금
  ├─ SAV-001 적금
  └─ LOAN-001 대출
~~~

상품별 핵심 필드:

- 예금: 원금, 가입일, 만기일, 기본금리, 우대금리, 적용금리, 세전·세후 이자, 거래내역
- 적금: 기본금리, 우대조건, 조건 충족 상태, 금리 변경 이력, 안내 이력
- 대출: 상품명, 대출원금, 실행일, 만기일, 적용금리, 금리 유형, 잔액, 상환방식, 상환내역, 금리 변경 이력, 금리 안내 이력, 연체 여부

사용자가 실제 입금액과 적용금리를 모른다고 해도 문의와 조회 데이터에 있는 사실을 먼저 보여줍니다. 두 출처 모두에 없는 핵심 값만 상담창에서 질문합니다.

### SQLite와 Supabase의 경계

현재 SQLite는 실제 금융기관 DB가 아니라 데모용 가상 금융 데이터 저장소입니다.

- 파일: `server/finance/mock_bank.sqlite3`
- 기본 고객: `CUST-001`
- 계약: `DEP-001` 예금, `SAV-001` 적금, `LOAN-001` KB 직장인든든 신용대출
- 저장 범위: 고객, 상품·계약, 거래내역, 대출 상환내역, 금리 변경 이력, 안내 이력
- 접근 경로: `MockBankClient` → `Finance MCP` → 에이전트
- 접근 권한: 현재 세션 고객 소유 데이터만 읽기

대출 가상 데이터에는 상품명, 원금, 실행일, 만기일, 적용금리, 금리 유형, 잔액, 상환방식, 상환내역, 금리 변경 이력, 안내 이력, 연체 여부를 넣었습니다. `LOAN-001`의 안내 이력은 금리 변경 미안내 시나리오를 재현하기 위해 비어 있습니다.

로컬 단일 프로세스 데모만 운영한다면 Supabase는 필수가 아닙니다. 하지만 실제 배포를 전제로 하면 Supabase를 앱 상태 저장소로 도입하는 것이 다음 단계입니다. SQLite는 가상 금융 원장의 읽기용 데이터로 당분간 유지하고, 다음 데이터를 먼저 Supabase로 옮깁니다.

1. 사용자·인증·동의 상태
2. 민원·리포트·검토 결과
3. 감사 로그와 실행 이력

Supabase 도입 시에도 RAG 문서·corpus를 Supabase에 섞지 않고, Finance MCP Tool 인터페이스 뒤의 금융 데이터 구현만 교체할 수 있습니다. 즉 지금 당장 모든 파일과 가상 금융 데이터를 Supabase로 옮기는 것이 아니라, 배포에 필요한 영구 상태부터 연결합니다.

## 7. RAG 데이터와 검색

~~~text
data/
├─ regulations/       법령·감독규정·공통 약관
│  └─ law_api/        국가법령정보 API 원문
├─ products/          예금·적금·대출 상품설명서·금리표
├─ cases/             판례·분쟁조정 사례
├─ complaints/        금융 상담·민원 표현
├─ dictionary/        금융·법률 용어 설명
├─ corpus/            RAG용 JSONL
└─ evaluation/        회귀·평가용 입력
~~~

처리 단계:

~~~text
PDF·JSON·CSV·변환된 HWP
        ↓
server/rag/ingest.py
        ↓
조항·항목·사례·질문답변 단위 chunk
        ↓
server/rag/build_corpus.py
        ↓
목적별 corpus JSONL
        ↓
server/rag/retrieval.py
        ↓
RAG 후보 → 상품·시점·조항 검증 → 확정 근거
~~~

문서 전체를 일정 글자 수로 자르지 않고 법령 조·항·호, 약관 조항, FAQ 질문·답변, 사례의 사실·판단·결론, 상품설명서 섹션을 우선합니다. 제목·상위 장·예외·부칙·시행일은 가능한 경우 chunk 메타데이터에 함께 넣습니다.

### 시점 기반 검색

~~~json
{
  "document_type": "상품약관",
  "institution": "KB국민은행",
  "product_name": "예시 상품",
  "effective_from": "2024-01-01",
  "effective_to": "2024-12-31",
  "version": "3.1",
  "source_url": "https://example.com",
  "collected_at": "2026-07-30"
}
~~~

계약일·거래일이 있으면 effective_from <= 사건일, effective_to >= 사건일 조건으로 검색합니다. 다음 버전의 시행일을 확인한 경우 이전 버전의 effective_to를 다음 시행일 하루 전으로 계산할 수 있지만, 근거 없는 날짜를 임의로 만들지는 않습니다.

현재 검색은 IDF 가중 전문 검색을 기본으로 하고, 임베딩이 있는 경우에만 cosine 점수를 보조로 사용합니다. 여러 검색어는 RRF로 합칩니다. 임베딩이 null이어도 전체 검색이 멈추지 않습니다.

데이터 역할:

- 규정·약관·상품설명서·판례: 처리 결과의 근거
- complaints: 민원 표현 학습·라우팅·평가용, 법적 판단 근거 아님
- dictionary: 사용자 화면의 어려운 용어 설명용, 결정 근거 아님
- evaluation: 회귀 테스트용, 운영 답변에 직접 노출하지 않음

RAG 후보는 민원 트리의 별도 노드가 아닙니다. 최종 리포트의 판단 근거에 문서명·페이지·조항·원문 링크와 함께 표시하고, 사용자가 누르면 상세 원문을 확인합니다. 검색 점수·검색 방식·내부 chunk ID는 숨깁니다.

## 8. 결정과 리포트

IssueAnalysis는 민원 ID·상품·쟁점, focal·target, 사용자·Mock·파생 사실, 누락 사실, 검색 질의·근거 후보, 결정 상태·위험도·검토 여부, 리포트·후속 절차를 유지합니다.

결정 우선순위는 hold > amend > ask > proceed입니다.

- 진행 가능: 제공된 사실과 근거로 설명 가능
- 확인 필요: 결과를 바꿀 핵심 정보가 부족함
- 보완 필요: 파일·거래내역·계약 조건 등 증빙이 부족함
- 검토 대기: 근거 충돌·고위험·분쟁·사고 의심·공식 민원 요구

리포트 기본 형식:

~~~text
민원내용
처리결과
소비자 유의사항
제출 서류·후속 절차
판단 근거
  ├─ 근거 문서명
  ├─ 관련 조항·페이지
  ├─ 문서 시행일
  └─ 원문 링크
~~~

LLM은 근거 후보를 자연어로 정리하지만 숫자·금리·날짜는 Mock 데이터와 계산 결과를 우선합니다. 근거가 없거나 문서가 충돌하면 확정 표현 대신 확인 사항과 상담원 검토를 표시합니다.

## 9. 서버 API

~~~text
GET /dictionary/search
GET /mock/customers/{customer_id}/products
GET /mock/customers/{customer_id}/deposits
GET /mock/customers/{customer_id}/savings
GET /mock/customers/{customer_id}/loans
GET /mock/accounts/{account_id}/transactions
GET /mock/accounts/{account_id}/repayments
GET /mock/accounts/{account_id}/rate-history
GET /mock/accounts/{account_id}/notice-history
GET /health
POST /api/v1/cases/analyze
GET /api/v1/cases/{case_id}
GET /api/v1/reviews/queue
POST /api/v1/cases/{case_id}/review
GET /api/v1/cases/{case_id}/audit
GET /api/v1/admin/overview
GET /api/v1/admin/documents
GET /api/v1/admin/documents/{doc_id}
GET /api/v1/admin/search
GET /api/v1/admin/cases
GET /api/v1/admin/cases/{case_id}
GET /api/v1/admin/audit
~~~

POST /api/v1/cases/analyze가 전체 파이프라인의 진입점이며 CaseAnalysis를 반환합니다.

## 10. 클라이언트와 저장

client/는 React와 @xyflow/react를 사용합니다.

- 마이 페이지: 최근 민원 상태와 내 금융 상황
- Chat/민원 흐름: 처음에는 빈 트리, 분석 후 민원 분기 생성
- 완료 민원: 생성된 리포트, 근거 자료, 용어 설명
- 관리자: 대시보드, 지식 문서, 검색 테스트, 민원 검토, 실행·감사 로그

트리에는 민원·확인된 사실·계산 결과를 표시하고, RAG 후보는 리포트 근거 카드와 상세 Drawer로 표시합니다. ask나 amend처럼 사용자가 입력해야 하는 단계만 빨간색으로 강조합니다.

관리자 화면은 현재 read-only 운영 콘솔입니다. 문서 목록은 로컬 corpus에서 만들고, 검색 테스트는 동일한 SearchIndex를 사용하며, 민원 검토와 감사 로그는 현재 서버 메모리 저장소를 조회합니다. 자동 크롤러·문서 삭제·프롬프트 배포·권한 변경은 아직 연결하지 않았습니다.

브라우저는 최근 사례를 localStorage에 최대 30개 보관합니다. 서버의 CASE_STORE는 현재 메모리 저장이므로 재시작하면 서버 사례 조회가 사라집니다. 영구 저장은 Supabase 또는 별도 DB 연결 때 추가합니다.

## 11. 디렉터리와 실행

~~~text
client/src/              React 화면·XYFlow·API 호출
server/app.py            FastAPI 오케스트레이션
server/agents/           Case Builder·RAG·검증·결정·응답
server/policy/           LLM Policy Gateway
server/rag/              ingest·corpus·retrieval
server/mcp/finance/      Finance MCP 서버·클라이언트
server/finance/          Mock Bank SQLite·데이터 접근
server/scripts/          데이터 변환·검증
server/tests/            회귀 테스트
data/                    RAG 원천 문서와 corpus
docs/                    요구사항·구조·구현 이력
~~~

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn server.app:app --reload
cd client
npm install
npm run dev
~~~

~~~powershell
python -m unittest discover -s server/tests -p "test_*.py"
~~~

## 12. 현재 다음 작업

1. 배포 전 Supabase에 사용자·민원·리포트·검토·감사 로그 영구 저장소 연결
2. 계약일·거래일 기반 문서 버전 필드 보강
3. 대출·예금·적금 회귀 평가 케이스 확대
4. 근거 인용 정확도와 상충 문서 테스트
5. 필요할 때만 임베딩 일괄 생성

여러 에이전트를 더 추가하기보다 현재 흐름의 관측성·평가·데이터 품질을 먼저 개선합니다.
