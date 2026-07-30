# PRD: KB Key Buddy 금융소비자 보호 기능

문서 상태: 현재 구현 기준

최종 지원 상품: 예금·적금·대출

## 1. 제품 개요

KB Key Buddy는 금융 앱 안에서 사용자가 입력한 복합 금융 문의와 현재 로그인 세션에 연결된 내 금융정보를 함께 확인하고, 규정·약관·상품설명서·판례·분쟁조정 사례를 근거로 민원 처리 방향을 안내하는 기능이다.

이 서비스는 금융회사의 최종 판단이나 민원 접수를 자동으로 대신하지 않는다. 확인된 사실과 근거를 구분하고, 정보가 부족하거나 위험한 경우에는 질문·보완·검토 대기로 중단한다.

현재는 실제 은행 내부 시스템을 연동하지 않는다. 가상 고객·계약·거래 데이터를 SQLite 기반 Mock Bank에 저장하고 Finance MCP가 읽기 전용 금융 Tool로 제공한다.

## 2. 제품 목표

### 사용자 목표

- 여러 금융상품에 대한 문의를 한 번에 입력한다.
- 예금·적금·대출별로 민원이 자동 분리되는 과정을 확인한다.
- 사용자가 이미 입력했거나 내 금융정보에서 확인된 값을 다시 질문받지 않는다.
- 계약조건·거래내역·규정·약관·사례를 하나의 판단 흐름에서 확인한다.
- 어려운 금융 용어를 쉽게 이해한다.
- 처리결과·소비자 유의사항·필요 서류·후속 절차를 확인한다.

### 시스템 목표

- 민원별 issue_id를 처음부터 리포트까지 유지한다.
- 사용자 진술, 내 금융정보, RAG 후보, 검증된 근거를 구분한다.
- 검색 후보만으로 법적 책임·환급·배상을 확정하지 않는다.
- 모든 LLM 호출이 로컬 정책 Gateway를 통과하도록 한다.
- 고위험·충돌·저신뢰 결과를 Human Review 대상으로 표시한다.
- RAG 문서의 상품 범위와 적용 시점을 검색에 반영한다.

## 3. 공식 지원 범위

### 정식 지원

- 예금
- 적금
- 대출

### 라우팅만 가능하거나 검토 대기로 보내는 상품

라우터는 펀드·ELS·보험·공통 표현도 인식할 수 있지만, 현재 MVP의 전체 분석·Mock 금융정보·리포트 품질 보장은 예금·적금·대출에 한정한다. 지원 범위 밖 상품은 content scope와 Policy Gate에서 보완 또는 검토 대기로 처리한다.

### 제외

- 실제 국민은행·금융회사 내부 시스템 연동
- 실제 고객·계좌·주민등록번호·카드번호 수집
- 외부 금융 API를 통한 실거래 조회
- 금융회사·금융감독기관 민원 자동 제출
- 계좌·계약 변경, 환불·취소·이체 실행
- 환급액·배상액·승소 가능성의 확정
- 고객 신용도 또는 대출 승인 여부의 확정
- 근거 없는 웹 검색 결과의 판단 사용

## 4. 사용자 화면

클라이언트는 React와 XYFlow 기반이며 hash 라우팅으로 세 화면을 제공한다.

### 4.1 마이 페이지

- 최근 민원 목록
- 민원별 승인·확인중·보완 필요·검토 대기 상태
- 예금·적금·대출 계약 요약
- 상품명·원금·잔액·적용금리·만기·상환상태 표시
- 서버 Mock API에서 현재 가상 고객의 금융정보 조회

### 4.2 민원 상담 페이지

- 최초 화면에는 노드가 없다.
- 오른쪽 채팅창에 사용자가 문의를 입력한다.
- 분석 후 왼쪽에 복합 문의 루트와 issue 노드가 생성된다.
- issue를 클릭하면 현재 상담 섹션이 바뀐다.
- 채팅 답변·선택에 따라 사용자 사실·계산 결과·결정 노드가 추가된다.
- 추가 정보가 필요한 단계는 채팅 질문과 빨간 상태로 표시한다.
- 노드는 드래그·확대·축소·화면 이동이 가능하다.
- issue를 더블클릭하면 판단 리포트 Drawer가 열린다.
- 사실 노드를 더블클릭하면 해당 사실·대화·근거 상세 Drawer가 열린다.

### 4.3 생성된 민원 페이지

처리가 완료된 issue의 리포트만 표시한다.

- 민원내용
- 처리결과
- 소비자 유의사항
- 금융 용어 설명
- RAG 근거 기반 결론
- 근거 문서명·페이지·조항·적용기간
- 근거 카드를 클릭하면 상세 내용 표시

검색 점수·검색 방식·내부 chunk ID는 일반 사용자 화면에 기본 노출하지 않는다.

## 5. 대표 사용자 시나리오

### 5.1 복합 문의 입력

사용자:

~~~text
예금 만기 이자로 30만원을 예상했지만 실제로는 279,180원만 입금됐습니다.
가입금액은 1,000만원이고 적용금리는 3.3%였습니다.
또 적금은 자동이체 조건을 충족하지 못해 우대금리가 빠졌는데 관련 안내를 받지 못했습니다.
계약 조건과 약관, 거래내역을 함께 확인해주세요.
~~~

### 5.2 Case Builder 결과

~~~text
복합 금융 문의
├─ A. 예금 만기 이자 금액 불일치
└─ B. 적금 우대금리 미적용·안내 미수신
~~~

사용자가 이미 입력한 다음 값은 다시 질문하지 않는다.

- 예상 이자: 300,000원
- 실제 입금액: 279,180원
- 가입금액: 10,000,000원
- 적용금리: 3.3%

현재 로그인 세션의 Finance MCP에서 더 신뢰할 수 있는 거래·계약 사실을 확인할 수 있으면 해당 값을 우선 표시한다. 예를 들어 사용자가 실제 지급액을 기억하지 못한다고 말해도 다음처럼 안내한다.

~~~text
현재 확인된 정보는 실제 입금액 279,180원,
가입금액 10,000,000원, 적용금리 연 3.3%입니다.
얼마로 예상하셨습니까?
~~~

사용자 입력과 MCP 정보에 없는 값만 질문한다. 예치기간·예상 금액의 세전·세후 여부처럼 판단에 필요한 값이 양쪽에 없을 때만 ask를 생성한다.

### 5.3 사실·계산·근거 처리

예금 이슈는 다음 순서로 처리한다.

1. Finance MCP에서 계좌·계약·거래내역을 읽는다.
2. 사용자의 예상 이자와 실제 지급액을 구분한다.
3. 원금·금리·기간·세율을 이용해 결정적 계산을 수행한다.
4. RAG에서 상품설명서·예금 약관·공통 규정·사례 후보를 검색한다.
5. 상품·사건일·시행일·조항을 검증한다.
6. Logic Verification이 확인된 사실·비교 조건·미확인 정보를 구분한다.
7. Policy Gate가 proceed·ask·amend·hold를 결정한다.
8. Response Agent가 리포트를 작성한다.

RAG 후보자료는 트리의 별도 사실 노드로 만들지 않는다. 검색 후보는 리포트의 판단 근거 영역에 모으고, 사용자가 선택했을 때 문서 상세를 보여준다.

### 5.4 정보 부족

사용자:

~~~text
예금 이자가 예상보다 적게 들어왔어요.
~~~

내 금융정보가 있으면 실제 지급액·가입금액·적용금리를 먼저 알려주고 예상 이자만 질문한다. 내 금융정보가 없거나 동의되지 않았으면 그때만 실제 지급액·가입금액·금리를 질문한다.

### 5.5 고위험 민원

명의도용·본인 미신청 거래·사기 의심·사실 충돌·지원 범위 밖 상품은 자동으로 결론을 확정하지 않는다.

- risk_level을 high 또는 critical로 설정한다.
- human_review_required를 true로 설정할 수 있다.
- Policy Gate가 hold를 선택한다.
- 사용자는 검토 대기 상태와 확인이 필요한 이유를 본다.

## 6. 현재 아키텍처

~~~text
클라이언트 React/XYFlow
        ↓
FastAPI /api/v1/cases/analyze
        ↓
Case Builder Agent
 ├─ Issue Splitter
 ├─ Focal Builder
 ├─ 필수 사실 추출
 └─ 상품 연결
        ↓
Evidence & Decision Agent
 ├─ 현재 세션·조회 동의 확인
 ├─ Finance MCP 금융정보 조회
 ├─ 결정적 계산
 ├─ LLM RAG Query 생성
 ├─ 로컬 RAG 검색
 ├─ 적용기간·상품·문서 유형 필터
 └─ Logic Verification
        ↓
Deterministic Policy Gate
 ├─ proceed: 진행
 ├─ ask: 확인중
 ├─ amend: 보완 필요
 └─ hold: 검토 대기
        ↓
Response Agent
 ├─ 민원내용
 ├─ 처리결과
 ├─ 소비자 유의사항
 ├─ 제출 서류
 └─ 후속 절차
        ↓
CaseAnalysis JSON
        ↓
React Flow 트리·채팅·리포트 화면
~~~

### 실제 에이전트 3개

| 에이전트 | 구현 역할 | 주요 파일 |
|---|---|---|
| Case Builder Agent | 문의 분리·상품 분류·focal·target·필수 사실·라우팅 신뢰도 생성 | server/agents/router.py, focal_builder.py, facts.py |
| Evidence & Decision Agent | Finance MCP 조회·RAG·사실 대조·Logic Verification·Policy Gate 입력 구성 | server/app.py, mock_customer_data_resolver.py, rag_query.py, logic_verification.py |
| Response Agent | 민원내용·처리결과·유의사항·절차 리포트 생성 | server/agents/report_composer.py, response_composer.py |

Issue Splitter와 Focal Builder는 Case Builder 내부 단계다. My Info Resolver, RAG Retriever, Calculator, Logic Graph, Policy Gate, LLM Policy Gateway는 에이전트가 아니라 일반 모듈 또는 Tool이다.

## 7. LLM Policy Gateway

### 목적

모든 Gemini 요청이 정책 검사를 통과하도록 LLM 호출을 한 곳으로 모은다. 별도 LLM을 추가 호출하지 않으며, OPA나 외부 정책 서버도 사용하지 않는 로컬 결정적 모듈이다.

파일:

~~~text
server/policy/__init__.py
server/policy/gateway.py
~~~

### 연결된 LLM 단계

| 단계 | 용도 |
|---|---|
| issue_splitter | 복합 문의를 issue로 분리 |
| rag_query | 원문을 RAG 검색어로 변환 |
| logic_verification | 사실·계약·RAG 후보의 연결 검증 |
| report_composer | 리포트 문장 구성 |

현재 server에서 외부 provider의 generate_content를 직접 호출하는 곳은 Gateway뿐이다.

### Gateway 처리

~~~text
LLM 호출 요청
   ↓
허용된 단계인지 확인
   ↓
직접 식별자 마스킹
   ├─ 주민등록번호
   ├─ 계좌번호
   ├─ 카드번호
   ├─ 전화번호
   └─ 이메일
   ↓
Gemini 호출
   ↓
출력 개인정보 재검사
   ↓
JSON 형식 검증
   ↓
호출 단계·정책 버전·마스킹 수·해시 로그
~~~

금액·금리·기간·날짜는 금융 판단에 필요한 값이므로 마스킹하지 않는다. 이름의 일반적인 의미 기반 개인정보 탐지는 아직 구현하지 않았고, 현재는 직접 식별자 패턴과 세션 범위 통제로 보호한다.

Gateway 또는 LLM 호출이 실패하면 각 에이전트가 결정적 fallback을 사용한다. 따라서 LLM 장애가 발생해도 근거 없는 LLM 결과로 진행하지 않는다.

### 기존 Policy Gate와의 차이

- LLM Policy Gateway: LLM 호출 전후의 보안·마스킹·출력 형식 통제
- Deterministic Policy Gate: 분석 결과를 proceed·ask·amend·hold로 결정

두 단계는 분리되어야 한다. 전자는 LLM 호출을 보호하고, 후자는 금융 민원의 다음 행동을 결정한다.

## 8. Finance MCP

Finance MCP는 금융 데이터를 보관하는 에이전트가 아니다. 현재 가상 금융 데이터와 결정적 계산 함수를 MCP Tool로 노출하는 읽기 전용 연결 계층이다.

### 전송 방식

- 기본값: inprocess
- 검증용: stdio
- 환경변수: FINANCE_MCP_TRANSPORT=inprocess 또는 stdio

stdio 모드에서는 Python MCP SDK로 server.mcp.finance.finance_server를 별도 프로세스로 실행한다.

### Tool

| Tool | 역할 |
|---|---|
| get_my_profile | 현재 세션 고객·조회 동의 상태 |
| get_my_products | 예금·적금·대출 요약 |
| get_my_deposits | 예금 계약 |
| get_my_savings | 적금 계약 |
| get_my_loans | 대출 계약·잔액·상환조건 |
| get_my_transactions | 계좌 거래내역 |
| get_my_repayments | 대출 상환내역 |
| get_my_rate_history | 금리·우대조건 변경 이력 |
| get_my_notice_history | 안내 발송·수신 이력 |
| calculate_interest | 원금·금리·기간·세율 기반 이자 계산 |

모든 Tool은 읽기 전용이다. 민원 제출·계좌 변경·계약 변경·외부 전송 Tool은 없다.

### 고객 범위

브라우저와 LLM은 고객 ID를 추측하지 않는다. 현재 데모에서는 session-user가 CUST-001로 매핑된다. Tool은 customer_ref와 account_id의 소유권을 확인한 뒤 결과를 반환한다.

~~~text
session-user
   ↓
CUST-001
   ↓
Finance MCP
   ↓
본인 예금·적금·대출·거래·이력만 조회
~~~

현재는 데모 세션 매핑이다. 실제 앱에서는 인증 세션·동의 토큰·권한 시스템으로 교체해야 한다.

## 9. Mock 금융 데이터

파일:

~~~text
server/finance/
├─ mock_data.py
├─ mock_bank.sqlite3
└─ __init__.py
~~~

### 고객

~~~json
{
  "customer_id": "CUST-001",
  "name": "김민지",
  "authenticated": true,
  "consent_status": "granted"
}
~~~

### 예금

~~~json
{
  "account_id": "DEP-001",
  "customer_id": "CUST-001",
  "product_type": "deposit",
  "product_name": "KB Star 정기예금",
  "opened_at": "2025-08-01",
  "maturity_at": "2026-08-01",
  "principal": 10000000,
  "base_rate": 0.031,
  "preferential_rate": 0.002,
  "applied_rate": 0.033,
  "gross_interest": 330000,
  "tax": 50820,
  "net_interest": 279180,
  "status": "matured"
}
~~~

### 적금

적금에는 기본금리·우대금리·우대조건 충족 여부·금리 변경 이력·안내 이력을 저장한다. 자동이체 조건 미충족과 안내 이력 부재를 별도 사실로 비교할 수 있다.

### 대출

대출에는 다음 필드를 저장한다.

- 대출상품명
- 대출원금
- 실행일
- 만기일
- 적용금리
- 금리 유형
- 현재 잔액
- 상환 방식
- 상환 내역
- 금리 변경 이력
- 금리 안내 이력
- 연체 여부

Supabase는 아직 연결하지 않았다. 현재 데모와 테스트에는 로컬 SQLite가 사용된다. 서버 재시작 후 CaseAnalysis를 보존하는 영속 Case Store는 아직 구현되지 않았다.

## 10. RAG 데이터와 처리 구조

### 원천 데이터

~~~text
data/
├─ regulations/
│  └─ law_api/
├─ products/
│  ├─ deposit/
│  ├─ savings/
│  ├─ loan/
│  ├─ rates/
│  ├─ fund/
│  └─ isa/
├─ cases/
├─ complaints/
│  └─ aihub_25_finance_consulting/
├─ dictionary/
├─ corpus/
│  ├─ regulations.jsonl
│  ├─ products.jsonl
│  ├─ cases.jsonl
│  ├─ glossary.jsonl
│  ├─ all.jsonl
│  └─ manifest.json
└─ evaluation/
~~~

### 데이터별 용도

| 위치 | 용도 | 판단 근거 여부 |
|---|---|---|
| regulations | 법령·공통 규정·법령 API 원문 | 사용 |
| products | 예금·적금·대출·금리표·상품설명서 | 사용 |
| cases | 판례·분쟁조정 사례 | 사용 |
| complaints | 상담·민원 표현과 라벨 | RAG 근거로 사용하지 않음 |
| dictionary | 금융 용어 쉬운 설명 | 표시용 |
| evaluation | 회귀·정확도 테스트 | 사용하지 않음 |

AIHub 메타데이터 MCP는 사용하지 않는다. 필요한 AIHub 데이터는 직접 다운로드하여 data/complaints에 보관한다. Finance MCP는 AIHub 데이터가 아니라 현재 사용자의 가상 금융정보를 제공한다.

### ingest와 corpus

~~~text
PDF·법령 API JSON·판례 CSV
        ↓
server/rag/ingest.py
        ↓
server/rag/chunks.jsonl
        ↓
server/rag/build_corpus.py
        ↓
data/corpus/*.jsonl
~~~

PDF는 페이지 단위와 문서 섹션을 기준으로 청크화한다. 법령 API JSON은 조문·시행일·개정 정보를 읽는다. HWP 판례는 현재 직접 ingest하지 않고 cases/cases.csv로 변환한 뒤 corpus에 포함한다.

검색 런타임은 data/corpus/all.jsonl을 사용할 수 있고, 원천 변경 시 server/rag/chunks.jsonl을 다시 생성한다.

### 현재 검색 방식

- 한국어·영문 토큰 기반 full-text 검색
- IDF 가중치
- 상품 범위 필터
- effective_from·effective_to 기반 시점 필터
- 여러 focused query 검색
- RRF로 결과 결합
- embedding 필드가 있으면 선택적으로 vector 점수 결합

현재 corpus는 임베딩을 필수로 생성하지 않는다. 대부분의 embedding 값은 null이며, full-text 검색이 기본이다. 성능 개선이 필요하면 embedding 생성과 vector index를 추가한다.

### 시점 기반 검색

문서에 적용기간이 있으면 다음 조건을 적용한다.

~~~text
effective_from <= 사건 기준일
effective_to >= 사건 기준일
~~~

법령 API에서 시행일·개정일을 읽을 수 있는 경우 메타데이터에 반영한다. 다음 버전의 시행일을 확인할 수 있을 때 이전 버전의 effective_to를 다음 시행일 하루 전으로 계산한다. PDF에 날짜가 없으면 임의로 시행기간을 만들지 않고 null로 둔다.

### 검색 결과와 리포트

검색 결과는 EvidenceRef로 반환한다.

~~~json
{
  "doc_id": "doc-001",
  "chunk_id": "doc-001-p4-c1",
  "path": "local:regulations/law.pdf",
  "page": 4,
  "section": "제19조",
  "score": 0.82,
  "snippet": "관련 조문 일부",
  "effective_from": "2024-01-01",
  "effective_to": "2025-03-31",
  "match_type": "full_text"
}
~~~

후보자료는 Logic Verification 전까지 RAG_CANDIDATE다. 후보가 있다는 이유만으로 proceed하지 않는다. Response Agent가 사용할 수 있는 근거 chunk_id도 검색 결과에 존재하는 값으로 제한한다.

## 11. Case 데이터 계약

핵심 스키마는 server/schemas.py에 정의한다.

### IssueInput

- issue_id
- product
- issue_type
- text
- focal
- target
- required_facts
- 사용자 입력 facts
- routing_confidence
- routing_method

### IssueAnalysis

- issue_id
- product
- issue_type
- focal·target
- mock_data
- facts
- missing_facts
- fact_resolution
- retrieval_query
- evidence_refs
- decision
- risk_level
- risk_reasons
- human_review_required
- logic_verification
- report
- content_scope
- next_steps

### 출처 구분

| 출처 | 의미 |
|---|---|
| 사용자 진술 | 사용자가 직접 입력한 값 |
| MCP 확인 사실 | 현재 고객 계약·거래·이력에서 확인한 값 |
| 계산 결과 | 결정적 계산 Tool 또는 서버 계산 |
| RAG 후보 | 검색되었으나 검증 전인 문서 |
| 검증 근거 | 상품·시점·조항 범위를 확인한 자료 |
| LLM 생성 문장 | 위 자료를 설명한 문장일 뿐 새로운 사실이 아님 |

## 12. Decision Gate

결정 우선순위는 다음과 같다.

~~~text
hold > amend > ask > proceed
~~~

### proceed

필수 사실과 관련 근거가 있고, 고위험 신호·사실 충돌이 없는 경우.

### ask

예상 금액·기간·세전·세후 기준처럼 판단에 필요한 핵심 사실이 없고, 사용자 또는 MCP에서 확인할 수 없는 경우.

### amend

입력 범위·마스킹·증빙 보완·사용자 확인이 필요한 경우.

### hold

명의도용·사기 의심·사실 충돌·지원 범위 밖 상품·중대한 위험 신호·전문가 검토 필요 상황.

라우팅 신뢰도가 0.6 미만이면 위험도를 높이고 추가 확인 또는 검토 대상으로 보낸다. 0.6 이상 0.8 미만이면 medium 위험도로 기록한다.

## 13. API

### Case API

| Method | Path | 역할 |
|---|---|---|
| POST | /api/v1/cases/analyze | 문의 분석, CaseAnalysis 생성 |
| GET | /api/v1/cases/{case_id} | 분석 결과·트리·리포트 조회 |
| POST | /api/v1/cases/{case_id}/review | Human Review 결과 반영 |
| GET | /api/v1/cases/{case_id}/audit | Case 감사 이벤트 조회 |
| GET | /api/v1/reviews/queue | 검토 대기 issue 목록 |

### Mock 금융 API

| Method | Path |
|---|---|
| GET | /mock/customers/{customer_id}/products |
| GET | /mock/customers/{customer_id}/deposits |
| GET | /mock/customers/{customer_id}/savings |
| GET | /mock/customers/{customer_id}/loans |
| GET | /mock/accounts/{account_id}/transactions |
| GET | /mock/accounts/{account_id}/repayments |
| GET | /mock/accounts/{account_id}/rate-history |
| GET | /mock/accounts/{account_id}/notice-history |

### 기타

- GET /dictionary/search
- GET /health

브라우저는 MCP를 직접 호출하지 않는다. 브라우저는 FastAPI를 호출하고, 서버가 Finance MCP와 RAG를 조정한다.

## 14. 서버 디렉터리 구조

~~~text
server/
├─ app.py
├─ schemas.py
├─ policy/
│  └─ gateway.py
├─ agents/
│  ├─ rules/
│  ├─ router.py
│  ├─ focal_builder.py
│  ├─ facts.py
│  ├─ logic_graph.py
│  ├─ rag_query.py
│  ├─ logic_verification.py
│  ├─ decision_gate.py
│  ├─ report_composer.py
│  ├─ response_composer.py
│  └─ mock_customer_data_resolver.py
├─ finance/
│  └─ mock_data.py
├─ mcp/finance/
│  ├─ finance_server.py
│  └─ client.py
├─ rag/
│  ├─ ingest.py
│  ├─ build_corpus.py
│  ├─ retrieval.py
│  └─ chunks.jsonl
├─ scripts/
└─ tests/
~~~

## 15. 클라이언트-서버 연결

클라이언트는 기본적으로 http://localhost:8000을 API 주소로 사용하고, VITE_API_BASE로 변경할 수 있다.

분석 요청:

~~~json
{
  "prompt": "사용자 문의 원문",
  "customer_id": "CUST-001"
}
~~~

응답의 issues 배열을 기준으로 XYFlow 노드와 채팅 상태를 만든다. 각 issue의 report·evidence_refs·risk_level·routing_confidence·human_review_required를 UI에 표시한다.

분석이 끝난 Case는 현재 브라우저 localStorage에 최대 30건을 저장한다. 따라서 클라이언트 같은 브라우저에서는 서버를 꺼도 목록이 남을 수 있지만, 서버의 CASE_STORE는 재시작하면 사라진다.

## 16. 보안·안전 원칙

- LLM은 고객 ID를 추측하지 않는다.
- 고객 범위는 Finance MCP Tool 내부에서 다시 확인한다.
- 금융 Tool은 읽기 전용이다.
- 검색 문서는 명령이 아니라 참고 데이터로 취급한다.
- HTML script·hidden text·외부 URL 자동 실행을 허용하지 않는다.
- RAG 후보를 검증 전 확정 근거로 표시하지 않는다.
- LLM이 배상·환급·사기·승인·법적 책임을 확정하지 못하게 한다.
- 출력에는 기본적으로 검색 점수·내부 chunk ID·프롬프트를 표시하지 않는다.
- LLM 호출 전후 직접 식별자를 마스킹한다.
- 정책 Gateway와 Decision Gate를 분리한다.
- MCP와 API 실패 시 안전한 fallback 또는 ask·hold를 사용한다.

## 17. 구현 과정과 시행착오

| 문제 | 원인 | 수정 |
|---|---|---|
| Issue Splitter와 Focal Builder가 별도 에이전트로 과도하게 나뉨 | 같은 문의 문맥을 여러 단계에서 반복 전달 | Case Builder Agent 내부 단계로 통합 |
| 대출이 초기 문서와 구현에서 빠짐 | 초기 MVP가 예금·적금 중심으로 시작됨 | 대출을 정식 지원 범위로 추가하고 계약·상환·금리·연체 필드와 Tool 추가 |
| RAG 후보가 트리 노드로 표시됨 | 후보자료·사실·판단을 같은 시각 요소로 모델링 | 후보는 리포트 판단 근거에 묶고 클릭 상세 Drawer로 표시 |
| 리포트가 이미 생성됐는데 추가 정보 필요라고 표시됨 | 결정 상태와 리포트 문구가 별도 fallback으로 구성됨 | Decision Gate 결과를 리포트 current_decision에 연결 |
| 사용자가 이미 적은 30만원·279,180원을 다시 질문함 | 채팅 단계가 사용자 입력과 Mock 금융정보를 통합하지 않음 | facts와 MCP 확인 값을 먼저 resolve하고 없는 값만 질문 |
| 2천만원이 원금인지 예상 이자인지 모호함 | 금액 질문의 의미가 명확하지 않음 | 예상 이자·가입 원금을 분리 질문하고 expected_basis 분기 추가 |
| PDF·HWP 원문이 깨지거나 빈 청크가 생김 | HWP를 PDF ingest에 억지로 넣음 | HWP는 별도 CSV 변환 후 cases corpus에 포함하고 원본은 보관 |
| corpus의 effective_from·effective_to가 null | PDF에 시행기간 메타데이터가 없거나 개정 이력이 부족함 | 법령 API 날짜를 우선 사용하고, 다음 버전 시행일이 확인될 때만 이전 버전 종료일을 계산 |
| JSON·HWP·상담 데이터를 모두 판단 corpus에 넣으려 함 | 데이터 용도가 섞임 | 규정·상품·사례만 판단 RAG, glossary는 설명용, complaints는 라우팅·평가용으로 분리 |
| RAG에 임베딩이 없어서 품질이 낮아 보임 | 초기에는 full-text 검색을 우선 구현 | IDF·상품 필터·시점 필터·다중 query·RRF를 기본으로 하고 embedding은 선택 필드로 남김 |
| Gemini 503으로 라우팅이 실패함 | 외부 모델 수요 급증·네트워크·키 문제 | LLM 실패 시 규칙 기반 라우팅과 결정적 fallback 사용 |
| LLM 호출부가 여러 파일에 흩어짐 | 단계별로 Gemini SDK를 직접 호출 | 네 단계 호출을 server/policy/gateway.py로 통합 |
| server 폴더가 agent·rag·MCP·스크립트로 혼재됨 | 초기 파일을 빠르게 추가함 | agents·finance·mcp·rag·scripts·tests로 이동 |
| 서버를 끄면 Case 기록이 사라짐 | CASE_STORE가 메모리 저장소임 | 현재 client localStorage로 브라우저 기록을 유지하고, 서버 영속 DB는 후속 과제로 남김 |
| CSV export와 생성 캐시가 저장소를 오염시킴 | 중간 산출물을 원천·런타임 데이터와 함께 추적 | 목적별 corpus를 기준으로 하고 불필요한 export·pycache를 제거 |

## 18. 현재 한계와 기술 부채

- CASE_STORE는 메모리 기반이라 서버 재시작 후 서버 API에서 이전 Case를 조회할 수 없다.
- 클라이언트 localStorage 기록은 브라우저·기기별이며 사용자 인증과 연결되지 않았다.
- 실제 로그인·조회 동의 시스템이 아니라 session-user → CUST-001 데모 매핑이다.
- LLM Gateway는 정규식 기반 직접 식별자 마스킹이며 이름·문맥형 개인정보 탐지는 제한적이다.
- 현재 기본 RAG는 full-text 기반이며 임베딩·vector DB는 선택 사항이다.
- data/corpus/all.jsonl과 server/rag/chunks.jsonl은 큰 생성 산출물이라 GitHub 저장 시 Git LFS 또는 빌드 시 생성 방식이 필요하다.
- 법령·약관의 모든 PDF에 정확한 시행기간이 채워지는 것은 아니다.
- Finance MCP는 실제 금융기관 API가 아니라 가상 SQLite 데이터다.
- 지원 범위 밖 상품은 전체 분석 품질을 보장하지 않고 hold 또는 scope 처리한다.
- 실제 상담원용 인증·권한·검토 화면은 최소 UI 수준이다.

## 19. 테스트와 완료 기준

### 현재 검증

- 서버 unittest 전체 통과
- Finance MCP inprocess·stdio Tool 테스트
- Mock 고객·예금·적금·대출·거래·상환·금리·안내 API 테스트
- router LLM 구조화 출력·규칙 fallback 테스트
- RAG query LLM·fallback 테스트
- Decision Gate 위험도·상태 테스트
- Response/Report composer 테스트
- Policy Gateway 개인정보 마스킹·단계 차단·JSON 검증 테스트
- React client npm run build 성공

### 완료 기준

- [x] 예금·적금·대출 상품 라우팅
- [x] 복합 문의 issue 분리
- [x] Mock 금융정보 조회
- [x] Finance MCP 읽기 전용 Tool
- [x] 거래·상환·금리·안내 이력 조회
- [x] 로컬 규정·상품·사례 RAG
- [x] 상품·시점 필터
- [x] Logic Verification
- [x] Deterministic Policy Gate
- [x] risk_level·risk_reasons·human_review_required
- [x] LLM Policy Gateway
- [x] 민원내용·처리결과·소비자 유의사항 리포트
- [x] 근거 상세 표시
- [x] React Flow 트리·채팅·리포트 화면
- [x] 클라이언트 API 연결
- [ ] 서버 Case 영속 저장
- [ ] 실제 인증·동의 시스템
- [ ] 상담원 전용 검토 UI
- [ ] 임베딩 생성·vector 검색 운영

## 20. 실행 방법

서버:

~~~powershell
cd C:/Users/WIN11/ROJENNIE
./.venv/Scripts/Activate.ps1
python -m uvicorn server.app:app --reload --port 8000
~~~

클라이언트:

~~~powershell
cd C:/Users/WIN11/ROJENNIE/client
npm run dev
~~~

RAG 재생성:

~~~powershell
python -m server.rag.ingest --data-dir data --output server/rag/chunks.jsonl
python -m server.rag.build_corpus --data-dir data --chunks server/rag/chunks.jsonl --output-dir data/corpus
~~~

서비스의 답변은 참고용 처리 방향이다. 최종적인 금융회사 책임·환급·배상 여부는 정식 금융 민원 또는 분쟁조정 절차에서 확인해야 한다.
