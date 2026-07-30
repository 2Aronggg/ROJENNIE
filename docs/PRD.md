# PRD: KB Key Buddy 금융소비자 보호 기능

## 1. 제품 개요

KB Key Buddy는 금융 앱 안에서 사용자가 입력한 복합 금융 문의와 연결된 **내 금융정보**를 함께 확인하고, 약관·상품설명서·규정·사례를 근거로 민원 처리 방향을 안내하는 기능이다.

실제 은행 내부 시스템은 연동하지 않는다. 로그인한 데모 사용자의 가상 고객·계약·거래 데이터를 DB 또는 Mock 데이터에 저장하고, 앱에서는 실제 내부 API처럼 조회한다.

대출은 구현 범위에서 제외한다. MVP의 상품 범위는 현재 `data/`에 있는 예금·적금·ELS 문서와 가상 금융정보다.

## 2. 해결하려는 문제

- 여러 금융 문제를 한 번에 입력하면 상품별 민원이 섞임
- 사용자가 이미 제공한 금액·금리·거래 사실을 챗봇이 다시 질문함
- 약관·상품설명서·규정·거래내역을 따로 확인해야 함
- 검색 후보자료가 판단 근거와 분리되어 리포트에서 추적하기 어려움
- 복잡한 금융 용어와 민원 절차를 이해하기 어려움

## 3. 목표 사용자

- 예금·적금·ELS의 이자, 금리, 우대조건, 안내 여부를 확인하려는 고객
- 금융회사 답변을 받았지만 계약 조건과 실제 거래내역을 비교하고 싶은 고객
- 민원 제출 전 필요한 사실·서류·후속 절차를 정리하려는 고객

## 4. MVP 범위

### 포함

- 로그인 세션과 연결된 가상 `내 금융정보` 조회
- 사용자 복합 문의의 민원별 분리
- 민원별 focal·target·필수 사실 추출
- Mock 고객·계약·거래·금리·안내 이력 조회
- 약관·상품설명서·규정·사례 RAG 검색
- Finance MCP를 통한 금융정보·RAG·계산 Tool 호출
- 선택적 법령 MCP를 통한 법령·판례 조회 및 인용 검증
- 계약 조건과 실제 지급액의 계산 비교
- 민원별 `proceed / ask / amend / hold` 결정
- `민원내용 / 처리결과 / 소비자 유의사항` 리포트
- 제출 서류·후속 절차 안내
- React Flow 민원 트리와 근거 상세 Drawer

### 제외

- 금융회사 내부 시스템의 실제 연동
- 대출 민원 처리
- 금융회사·금융감독기관에 민원 자동 제출
- 계좌·계약 변경 또는 금융거래 실행
- 확인되지 않은 환급액·배상액·승소 가능성 확정
- 근거 없는 웹 검색 결과를 금융 판단에 직접 사용

## 5. 사용자 시나리오

### 시나리오 A: 내 금융정보가 연결된 복합 문의

#### 사용자 입력

```text
예금 만기 이자로 30만원을 예상했지만 실제로는 279,180원만 입금됐습니다.
가입금액은 1,000만원이고 적용금리는 3.3%였습니다.
또 적금은 자동이체 조건을 충족하지 못해 우대금리가 빠졌는데 관련 안내를 받지 못했습니다.
계약 조건과 약관, 거래내역을 함께 확인해주세요.
```

#### 1) 내 금융정보 확인

서버 세션의 사용자를 `CUST-001` 가상 고객에 연결한다. LLM이나 사용자가 고객 ID를 추측·입력하지 않는다.

Finance MCP가 다음 Tool을 읽기 전용으로 호출한다.

```text
get_my_products()
get_my_transactions("DEP-001")
get_my_rate_history("SAV-001")
get_my_notice_history("SAV-001")
```

#### 2) Case Builder

```text
민원 A: 예금 만기 이자 금액 불일치
민원 B: 적금 우대금리 미적용 및 안내 미수신
```

각 민원에 대해 상품, focal, target, 필수 사실을 만든다.

#### 3) Evidence & Decision

`search_evidence` MCP Tool이 기존 RAG에서 약관·상품설명서·규정 후보를 검색한다. 검색 결과는 문서명·페이지·조항·짧은 인용문이 있는 구조화된 근거로 반환한다.

계약·거래 데이터와 사용자 진술을 비교하고, 이자 계산 Tool 결과와 근거자료를 Logic Verification에 전달한다.

#### 4) 결정

사용자가 예상 이자·실제 지급액·가입금액·적용금리를 이미 입력했으므로 같은 내용을 다시 질문하지 않는다. 예치기간처럼 정말 없는 값만 `ask`로 질문한다.

충분한 사실과 근거가 있으면 리포트를 생성한다. 사용자가 제공한 사실과 거래내역이 충돌하면 `hold` 또는 `ask`를 선택한다.

#### 5) 리포트

```text
민원내용
예금 만기 예상 이자와 실제 지급액이 다르고, 적금 우대금리 미적용 안내를 받지 못했다는 내용입니다.

처리결과
계약조건 기준 계산액, 실제 거래내역, 약관·상품설명서의 적용 조건을 비교한 결과를 설명합니다.

소비자 유의사항
금리·우대조건·세금·안내 이력에 따라 결과가 달라질 수 있으며, 필요한 거래내역과 안내 기록을 보관해야 합니다.
```

RAG 후보자료는 별도 노드로 만들지 않고 `판단 근거` 영역에 묶는다. 사용자가 근거를 누르면 문서 상세 Drawer를 연다.

### 시나리오 B: 정보가 부족한 문의

```text
예금 이자가 예상보다 적게 들어왔어요.
```

내 금융정보와 문의에 예상 금액·실제 지급액이 모두 없으면 챗봇이 필요한 질문을 한다.

```text
실제로 입금된 이자는 얼마였나요?
```

이미 사용자가 답한 값은 이후 단계에서 재질문하지 않는다.

### 시나리오 C: 고위험 문의

명의도용·본인 미신청 거래·보이스피싱이 의심되면 근거 검색 결과와 무관하게 `hold`로 보낸다. 일반적인 금융 판단을 이어가지 않고 즉시 안전 안내와 전문가 검토를 표시한다.

## 6. 처리 아키텍처

```text
사용자 로그인·조회 동의
        ↓
사용자 문의
        ↓
Case Builder Agent
 ├─ Issue Splitter
 ├─ Focal Builder
 └─ 필수 사실 추출
        ↓
FastAPI MCP Client
        ↓
Finance MCP Server
 ├─ My Info Tools
 ├─ Evidence/RAG Tools
 └─ Calculator Tool
        ↓
Evidence & Decision Agent
 ├─ 사용자 진술·내 금융정보 대조
 ├─ 근거 후보 관련성 검증
 ├─ 선택적 Korean Law MCP
 └─ Logic Verification
        ↓
Deterministic Policy Gate
        ↓
Response Agent
```

### 실제 에이전트는 3개

| 에이전트 | 역할 |
|---|---|
| Case Builder Agent | Issue Splitter, Focal Builder, 필수 사실 추출을 묶어 구조화된 민원 Case 생성 |
| Evidence & Decision Agent | MCP로 내 금융정보·RAG 근거를 조회하고 사실관계를 검증 |
| Response Agent | 검증 결과를 민원내용·처리결과·유의사항·절차로 작성 |

MCP Tool, 이자 계산, My Info Resolver, Logic Graph, Policy Gate는 에이전트가 아니라 도구·일반 모듈이다.

## 7. MCP 연결 설계

### Finance MCP Tools

| Tool | 설명 |
|---|---|
| `get_my_profile` | 현재 사용자와 조회 동의 상태 |
| `get_my_products` | 현재 사용자의 예금·적금·ELS |
| `get_my_transactions` | 계좌 거래내역 |
| `get_my_rate_history` | 금리·우대조건 변경 이력 |
| `get_my_notice_history` | 안내 발송·수신 이력 |
| `search_evidence` | 기존 RAG에서 근거 후보 검색 |
| `get_evidence` | 근거 문서 상세 조회 |
| `calculate_interest` | 이자·세금 계산 |

### RAG와 MCP의 관계

```text
MCP search_evidence 호출
        ↓
retrieval.py가 data/ 문서 검색
        ↓
근거 후보 반환
        ↓
관련성·시행일·상품 범위 검증
        ↓
Logic Verification
        ↓
Policy Gate와 Response Agent
```

MCP는 RAG 원문이나 임베딩을 대신 저장하지 않는다. 검색 기능을 표준 Tool로 노출할 뿐이다.

### 외부 법령 MCP

법령·판례 원문과 인용 검증이 필요할 때만 Korean Law MCP를 보조 근거로 사용한다. 상품 약관·상품설명서·금융 사례는 기존 RAG를 우선한다.

## 8. 데이터 구조

```json
{
  "case_id": "case_001",
  "session_id": "session_001",
  "customer_ref": "session-user",
  "consent_status": "granted",
  "issues": [
    {
      "issue_id": "issue_001",
      "product": "deposit",
      "issue_type": "maturity_interest_mismatch",
      "focal": ["contract", "transaction_statement"],
      "target": "maturity_interest",
      "user_statements": [],
      "verified_facts": [],
      "my_info_refs": ["DEP-001"],
      "evidence_refs": [],
      "missing_facts": [],
      "verification": {},
      "decision": {
        "control": "proceed",
        "reasons": []
      }
    }
  ]
}
```

`customer_ref`는 내부 고객 ID를 그대로 클라이언트에 노출하지 않는 세션 참조다. `my_info_refs`에는 필요한 계좌·상품만 연결한다.

## 9. 리포트 계약

모든 민원은 다음 순서로 작성한다.

1. 민원내용
2. 확인된 사실
3. 처리결과
4. 판단 근거
5. 소비자 유의사항
6. 필요한 제출 서류
7. 후속 절차

검색 점수·검색 방식·내부 프롬프트·고객 ID는 기본 리포트에 표시하지 않는다. 근거 상세를 선택한 경우에만 허용된 출처·페이지·조항·인용문을 보여준다.

## 10. API

| Method | Path | 역할 |
|---|---|---|
| `POST` | `/api/v1/cases/analyze` | 문의 분석 및 case 생성 |
| `GET` | `/api/v1/cases/{case_id}` | 민원 트리·리포트·근거 조회 |
| `POST` | `/api/v1/cases/{case_id}/review` | Human Review 결과 반영 |

MCP Tool 호출은 브라우저가 아니라 FastAPI가 수행한다.

## 11. 비기능 요구사항

- 개인정보는 최소 조회·최소 표시한다.
- 주민번호·계좌번호·카드번호·인증정보는 마스킹한다.
- 사용자가 이미 제공한 사실은 재질문하지 않는다.
- MCP 실패 시 근거 없는 판단으로 진행하지 않고 오류·보류 상태를 표시한다.
- 모든 MCP 호출은 `trace_id`와 Tool 이름을 서버 로그에 남긴다.
- 읽기 전용 Tool만 사용한다.
- 복합 민원은 `issue_id`를 끝까지 유지한다.
- 서버 재시작 후에도 민원 기록이 필요하면 SQLite 등 영속 저장소를 사용한다.

## 12. 평가 계획

- `complex_issue_75.json`의 하위 민원 수·상품·쟁점 일치율
- 사용자 입력 사실과 My Info 조회 사실의 재질문 방지율
- `search_evidence` 결과의 문서·페이지·조항 연결률
- 사건일과 시행일이 다른 문서의 차단 여부
- RAG 후보가 Logic Verification을 거치지 않고 판단에 사용되지 않는지
- 금액 계산 오류와 세금·금리·기간 필드의 출처 구분
- `ask / amend / hold / proceed` 결정 일관성
- 개인정보 원문 노출 여부
- MCP 장애 시 안전한 fallback 여부

## 13. 주의사항

이 서비스는 금융회사나 금융감독기관의 최종 판단, 법률 자문, 민원 자동 접수를 대신하지 않는다. 확인되지 않은 사실을 확정하지 않으며, 최종 판단은 정식 금융 민원·분쟁조정 절차를 통해 확인해야 한다.
