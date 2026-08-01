# Server

FastAPI 기반 오케스트레이터입니다. 브라우저 요청을 받아 세 개의 에이전트와 읽기 전용 MCP Tool을 순서대로 호출합니다.

## 처리 순서

```text
POST /api/v1/cases/analyze
        ↓
Case Builder Agent
 ├─ Issue Splitter
 ├─ Focal Builder
 ├─ 필수 사실 추출
 └─ 예금·적금·대출 상품 연결
        ↓
Evidence & Decision Agent
 ├─ Finance MCP: 계약·거래·상환·금리·안내 이력 조회
 ├─ RAG Retriever: 로컬 규정·약관·판례 검색
 ├─ Calculator Tool: 이자 계산
 ├─ 사실 대조
 ├─ 근거 관련성 검증
 └─ Logic Verification
        ↓
Deterministic Policy Gate
        ↓
Response Agent
```

MCP는 에이전트가 아닙니다. Finance MCP는 `mock_data.py`의 읽기 전용 금융 조회·계산 함수를 Tool로 노출하는 연결 계층입니다. [공식 Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## 디렉터리

```text
server/
├─ app.py                         FastAPI API
├─ schemas.py                     API·case schema
├─ agents/                        민원 분석 에이전트
│  ├─ pipeline.py                 전체 오케스트레이션
│  ├─ rules/                      Agent가 따라야 할 규칙 문서
│  ├─ router.py                   Case Builder 라우팅
│  ├─ focal_builder.py            Focal Builder
│  ├─ facts.py                    사실 충돌·누락 처리
│  ├─ logic_graph.py              민원 트리와 사실 관계
│  ├─ rag_query.py                RAG 질의 생성
│  ├─ logic_verification.py       근거·사실 검증
│  ├─ decision_gate.py            결정 상태 계산
│  ├─ question_builder.py         확인된 사실 기반 질문 구성
│  ├─ response_composer.py        최종 답변 구성
│  ├─ report_composer.py          리포트 구성
│  └─ mock_customer_data_resolver.py  내 금융정보 연결
├─ rag/                           금융 문서 ingest·corpus·검색
│  ├─ ingest.py
│  ├─ build_corpus.py
│  ├─ retrieval.py
│  └─ chunks.jsonl                생성된 중간 청크
├─ finance/                       가상 고객·계약·거래 데이터
│  ├─ mock_data.py
│  └─ mock_bank.sqlite3
├─ mcp/finance/                   Finance MCP 연결 계층
│  ├─ finance_server.py            Finance MCP Server
│  └─ client.py                    MCP Tool 호출 클라이언트
├─ scripts/                       데이터 수집·변환 스크립트
└─ tests/                         서버·에이전트 테스트
```

## Finance MCP Tools

초기에는 하나의 내부 MCP 서버만 사용합니다.

| Tool | 역할 | 데이터 출처 |
|---|---|---|
| `get_my_profile` | 현재 사용자·동의 상태 조회 | `mock_data.py` |
| `get_my_products` | 예금·적금·대출 상품 조회 | `mock_data.py` |
| `get_my_deposits` | 예금 계약 상세 조회 | `mock_data.py` |
| `get_my_savings` | 적금 계약 상세 조회 | `mock_data.py` |
| `get_my_loans` | 대출 계약 상세 조회 | `mock_data.py` |
| `get_my_transactions` | 거래내역 조회 | `mock_data.py` |
| `get_my_repayments` | 대출 상환내역 조회 | `mock_data.py` |
| `get_my_rate_history` | 금리 변경 이력 조회 | `mock_data.py` |
| `get_my_notice_history` | 안내 이력 조회 | `mock_data.py` |
| `calculate_interest` | 이자·세금 계산 | 결정적 함수 |

고객 ID는 문의에서 추출하지 않습니다. 서버 세션의 현재 사용자에 연결된 가상 고객만 조회합니다.

```text
session user
  → CUST-001
  → get_my_products()
  → 관련 account_id 선택
  → 거래·금리·안내 이력 조회
```

MCP Tool은 모두 읽기 전용입니다. 민원 제출, 이메일 전송, 계좌·계약 변경 Tool은 만들지 않습니다.

## RAG와 MCP의 관계

```text
rag/retrieval.py.search(query)
        ↓
rag/retrieval.py가 data/ 문서 검색
        ↓
evidence_id·문서명·페이지·조항·인용문 반환
        ↓
Evidence & Decision Agent
        ↓
Logic Verification
```

Finance MCP가 RAG 데이터를 대신 저장하지 않습니다. Finance MCP는 내 금융정보·계산 Tool이고, RAG는 `retrieval.py`가 `data/`에서 직접 검색합니다.

## 금융 데이터 저장소

현재 `server/finance/mock_bank.sqlite3`가 가상 금융 데이터의 저장소입니다. 실제 은행 내부 DB나 실제 고객정보가 아닙니다.

`MockBankClient
  → server/finance/mock_bank.sqlite3
  → FinanceMCPClient
  → Evidence & Decision Agent`

현재 기본 고객은 `CUST-001`이며 예금 `DEP-001`, 적금 `SAV-001`, 대출 `LOAN-001`을 가집니다. SQLite에는 고객, 상품·계약, 거래내역, 대출 상환내역, 금리 변경 이력, 안내 이력이 저장됩니다. `mock_data.py`의 가상 데이터를 기준으로 시작할 때 초기값을 보장하므로, 데모 데이터 수정은 이 파일에서 합니다.

로컬 단일 프로세스 데모에서는 SQLite로 충분하지만, 실제 배포에서는 Supabase를 앱 상태 저장소로 연결해야 합니다. 우선 민원·리포트·검토·감사 로그와 사용자 정보를 Supabase에 저장하고, 가상 금융 원장은 당분간 SQLite 읽기 전용으로 유지할 수 있습니다.

- 여러 사용자의 민원·리포트·검토 결과를 서버 재시작 후에도 보존해야 할 때
- 관리자와 상담원이 같은 사례를 공유해야 할 때
- 원격 배포와 로그인·권한 관리가 필요할 때

Supabase로 바꿀 때도 에이전트는 Finance MCP Tool만 호출하고, RAG 문서와 corpus는 별도 저장소로 유지합니다. 즉 DB 교체가 에이전트 로직 변경으로 번지지 않도록 현재 MCP 계약을 유지합니다. 배포 전에는 이 저장소 연결과 인증을 구현해야 합니다.

## Corpus

`data/corpus/`는 목적별 검색 단위입니다.

| 파일 | 용도 | 결정 근거 |
|---|---|---|
| `regulations.jsonl` | 법령·공통 규정 | 사용 |
| `products.jsonl` | 예금·적금·대출 등 상품 문서 | 사용 |
| `cases.jsonl` | HWP에서 추출한 판례·분쟁조정 사례 | 사용 |
| `glossary.jsonl` | 금융 용어 쉬운 설명 | 표시용 |
| `all.jsonl` | 위 corpus를 합친 런타임 인덱스 | 위 규정·상품·사례만 판단에 사용 |

민원 상담 JSON은 학습·평가와 질문 흐름 개선용으로만 유지합니다. 검색 근거와 상담 사례를 섞지 않기 위해 corpus에서 제외합니다.

corpus를 다시 만들 때:

```powershell
python -m server.rag.ingest --data-dir data --output server/rag/chunks.jsonl
python -m server.rag.build_corpus --data-dir data --chunks server/rag/chunks.jsonl --output-dir data/corpus
```

RAG는 한 개의 긴 검색어만 사용하지 않고, Case Builder 쟁점·상품·원문에서 만든 focused query들을 각각 검색한 뒤 IDF 기반 후보 점수와 RRF로 합칩니다. 용어 사전은 설명용 corpus라 판단 근거 검색에서 제외합니다. `similarity_score`, `search_method`, 내부 chunk ID는 기본 응답에 노출하지 않습니다.

## API

| Method | Path | 역할 |
|---|---|---|
| `POST` | `/api/v1/cases/analyze` | 문의 분석 및 case 생성 |
| `GET` | `/api/v1/cases/{case_id}` | 트리·리포트·근거 조회 |
| `POST` | `/api/v1/cases/{case_id}/review` | Human Review 결과 반영 |

## 상태

```text
proceed = 사실·근거가 충분하여 리포트 생성
ask     = 사용자에게 핵심 정보 추가 질문
amend   = 입력 마스킹·증빙 보완 필요
hold    = 고위험·명의도용·중대한 충돌로 검토 대기
```

Policy Gate는 LLM이 아니라 일반 코드로 최종 상태를 결정합니다. 사용자가 이미 입력한 값이나 Finance MCP로 확인된 값은 다시 질문하지 않습니다.

## 로컬 실행

```powershell
cd C:\Users\WIN11\ROJENNIE
\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
python -m uvicorn server.app:app --reload
```

MCP를 별도 프로세스로 실행하는 경우:

```powershell
python -m server.mcp.finance.finance_server
```

기본 개발 모드는 `inprocess`이며, 실제 MCP stdio 왕복이 필요하면 `FINANCE_MCP_TRANSPORT=stdio`를 설정합니다. 데이터 접근과 MCP Tool의 입출력 계약은 분리해 유지합니다.

## LLM

`GEMINI_API_KEY`가 있으면 구조화된 LLM 출력을 사용하고, 키·SDK·네트워크·응답 오류가 있으면 결정적 fallback으로 전환합니다. LLM은 고객 ID, 검증 사실, 이자 계산 결과를 임의 생성하지 않습니다.

모든 LLM 호출은 server/policy/gateway.py를 통과합니다. Gateway는 허용된 단계인지 확인하고, 이름·계좌번호·카드번호·전화번호·이메일을 마스킹한 뒤 호출하며, JSON 응답 형식과 호출 감사 정보를 검증합니다. Gateway 자체는 추가 LLM이나 외부 정책 서버를 호출하지 않습니다.

## 제외

- 금융회사 내부 시스템 실제 연동
- 외부 민원 자동 제출
- 계좌·계약 변경
- MCP를 통한 쓰기 작업
