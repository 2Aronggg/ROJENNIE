# KB Key Buddy 기술 아키텍처

문서 기준: 2026-08-02
범위: 현재 구현된 백엔드, 데이터, RAG, 평가/안전성 구조를 기준으로 작성합니다. UI 시연 HTML은 발표용 데모이며, 본 문서에서는 핵심 기술 구조만 다룹니다.

## 1. 시스템 개요

KB Key Buddy는 복합 금융 민원을 이슈 단위로 분리하고, mock 금융 데이터와 RAG 문서 근거를 함께 확인해 사용자에게 안전한 다음 행동을 안내하는 금융 민원 분석 시스템입니다.

핵심 설계 원칙:

- 복합 민원을 하나의 결론으로 뭉개지 않고 이슈 단위로 분리합니다.
- 사용자가 말한 사실, 시스템이 확인한 사실, 문서 근거, 유사 사례를 구분합니다.
- 검색 결과를 곧바로 결론으로 쓰지 않고 Logic Verification을 거칩니다.
- 법적 책임, 배상 가능성, 은행 과실은 자동 확정하지 않습니다.
- 근거가 부족하면 실패가 아니라 `ask` 또는 `hold`로 안전하게 멈춥니다.

현재 지원 범위:

- 예금
- 적금
- 대출

제외 범위:

- 실제 은행 내부 API 연동
- 실제 고객 계좌 변경/이체/민원 자동 제출
- 실고객 개인정보 저장
- 배상/위법/과실의 최종 판단

## 2. 전체 아키텍처

```text
Client / Demo UI
  -> FastAPI Server
     -> Case Builder
     -> Mock Customer Data Resolver / Finance MCP
     -> RAG Query Builder
     -> RAG Retrieval
     -> Logic Verification
     -> Decision Gate
     -> Report / Response Composer
  -> CaseAnalysis response
```

## 3. 데이터 레이어

| 데이터 | 위치 | 역할 |
| --- | --- | --- |
| mock 고객/계약/거래 데이터 | `server/finance/mock_bank.sqlite3`, `server/finance/mock_data.py` | 예금/적금/대출 계약, 거래, 금리, 안내 이력 조회 |
| 규정/법령 | `data/regulations`, `data/corpus/regulations.jsonl` | 직접 판단 근거 |
| 상품설명서/약관 | `data/products`, `data/corpus/products.jsonl` | 상품 조건, 금리, 수수료 등 직접 근거 |
| 분쟁조정/판례 사례 | `data/cases`, `data/corpus/cases.jsonl` | 유사 사례 참고 |
| 절차 안내 | `data/guides`, `data/corpus/guides.jsonl` | 민원 접수, 분쟁조정, 반환지원 등 다음 행동 안내 |
| 평가 데이터 | `data/evaluation` | retrieval 및 pipeline 검증 |

현재 corpus 규모:

- 65,764 chunks
- guides corpus 신설 반영
- glossary는 판단 근거 검색에서 제외하고 표시/설명 데이터로 분리

## 4. API 레이어

| Method | Path | 역할 |
| --- | --- | --- |
| `POST` | `/api/v1/cases/analyze` | 민원 입력 분석 |
| `GET` | `/api/v1/cases/{case_id}` | 분석 결과 조회 |
| `POST` | `/api/v1/cases/{case_id}/review` | 사람 검토 결과 반영 |

주요 응답 구조:

```text
CaseAnalysis
  - case_id
  - prompt
  - issues[]
      - issue_id
      - product
      - issue_type
      - facts
      - missing_facts
      - evidence_refs
      - logic_verification
      - decision
      - report
```

## 5. Agent 1~4와 실제 모듈

발표에서는 Agent 1~4라고 표현하지만, 현재 구현은 독립 autonomous agent가 아니라 Python 모듈과 deterministic function 중심의 파이프라인입니다.

| 발표용 Agent | 역할 | 실제 모듈 |
| --- | --- | --- |
| Agent 1 Case Builder | 복합 민원을 이슈와 fact 구조로 분리 | `router.py`, `focal_builder.py`, `facts.py` |
| Agent 2 Evidence/RAG | 검색 쿼리 생성 및 근거 문서 검색 | `rag_query.py`, `server/rag/retrieval.py` |
| Agent 3 Logic/Decision | 근거-결론 지지 검증 및 상태 결정 | `logic_verification.py`, `decision_gate.py` |
| Agent 4 Response | 안전 리포트와 사용자 응답 구성 | `report_composer.py`, `response_composer.py` |

권장 발표 표현:

> Agent는 논리적 파이프라인 단계입니다. 현재 프로토타입은 이 단계를 Python 모듈과 규칙 기반 로직으로 구현했고, 일부 생성 단계만 정책 게이트 뒤에서 LLM을 선택적으로 사용합니다.

## 6. Pipeline 상세

### 6-1. Case Builder

역할:

- 민원 원문에서 product와 issue_type 추정
- 복합 민원을 여러 issue로 분리
- issue별 focal, target, required_facts 구성
- 사용자가 직접 말한 fact를 `USER_STATED`로 기록

주요 모듈:

- `server/agents/router.py`
- `server/agents/focal_builder.py`
- `server/agents/facts.py`

### 6-2. Finance MCP / Mock Data Resolver

역할:

- 현재 세션의 mock 고객 `CUST-001` 기준 금융 데이터 조회
- 예금/적금/대출 계약, 거래내역, 금리 변경, 안내 이력 확인
- 조회된 값을 fact로 변환

mock 금융 데이터에서 생성된 fact는 사용자가 말한 것이 아니므로 `SYSTEM_INFERRED`로 태깅합니다.

주요 모듈:

- `server/agents/mock_customer_data_resolver.py`
- `server/finance/mock_data.py`
- `server/mcp/finance`

### 6-3. RAG Retrieval

역할:

- issue별 검색 쿼리 생성
- product, issue_type, 날짜 조건을 반영해 corpus 검색
- 중복 문서 제거
- EvidenceRef로 근거 후보 반환

최근 개선:

- pypdf PDF 추출을 `extraction_mode="layout"`으로 변경해 판례 PDF 토큰 깨짐 수정
- canonical doc_id 기반 중복 정리
- guides corpus 추가
- glossary는 판단 검색에서 제외

평가 결과:

| 구분 | Recall@5 |
| --- | --- |
| cases | 93.8% (15/16) |
| products | 100.0% (20/20) |
| guides | 100.0% (6/6) |
| 전체 | 97.6% (41/42) |

### 6-4. Logic Verification

역할:

- 검색 결과가 결론을 실제로 지지하는지 검증
- direct evidence, precedent reference, procedure guide를 구분
- claim-support chain 생성

Support chain:

```text
claim
  -> supporting_evidence[]
  -> inference_type
  -> evidence_role
  -> allowed_in_final
```

`inference_type`:

- `direct_match`
- `analogical`
- `unverified`

`evidence_role`:

- `direct_evidence`
- `precedent_reference`
- `procedure_guide`
- `unknown`

### 6-5. Decision Gate

Decision Gate는 LLM이 아니라 deterministic policy logic입니다.

상태:

| 상태 | 의미 |
| --- | --- |
| `proceed` | 확인된 사실과 직접 근거 범위에서 다음 단계 안내 가능 |
| `ask` | 추가 사실 또는 직접 근거 필요 |
| `amend` | 마스킹/입력 보완/표현 범위 조정 필요 |
| `hold` | 자동 판단 중지, 사람 검토 필요 |

추가된 감사 기준:

- 직접 근거 없음 + `proceed`는 `ask`로 강등
- 유사 사례만 있음 + `proceed`는 `ask`로 강등
- `unverified` claim은 audit log에 risk flag로 기록
- `proceed`는 결론 확정이 아니라 제한된 다음 단계 안내입니다.

### 6-6. Report Composer

역할:

- issue별 리포트 생성
- 근거 없는 단정 표현 제한
- 사용자에게 필요한 다음 행동 안내

차단/완화 표현:

- 배상 가능
- 배상액
- 보상 가능
- 은행 잘못
- 위법
- 책임 인정
- 반드시 지급

허용 표현:

- 확인된 사실 기준
- 추가 확인 필요
- 유사 사례 참고
- 접수/분쟁조정/반환지원 등 다음 행동 안내

## 7. LLM 사용 방식

LLM은 선택적 보조 수단입니다.

사용 가능 단계:

- issue splitting 보조
- RAG query 생성 보조
- logic summary 초안
- report 문장 초안

안전장치:

- 모든 LLM 호출은 `server/policy/gateway.py` 통과
- PII 마스킹
- 허용 stage 확인
- JSON schema 검증
- 금지 표현 필터
- 실패 시 fallback 사용

LLM이 해서는 안 되는 일:

- 고객 ID 생성
- 거래 사실 생성
- 배상/위법/과실 확정
- 최종 control override

## 8. 평가/검증

현재 검증 요약:

- retrieval 평가셋: 42문항
- 전체 Recall@5: 97.6%
- 테스트 수: 75개
- `test_facts.py`: source_type provenance 검증
- `test_logic_audit.py`: 근거 없음/유사 사례-only proceed 차단 검증

검색 성능과 판단 정확도는 분리해서 봅니다.

- Recall@5: 올바른 문서가 top-5 안에 들어오는가
- Support verification: 그 문서가 실제 claim을 직접 지지하는가
- Decision safety: 근거 부족 상태가 proceed로 새지 않는가

## 9. 배포 관점

현재 구조는 로컬/시연 환경에 적합합니다.

로컬:

- FastAPI
- local JSONL corpus
- mock SQLite bank
- optional Gemini API

향후 production 방향:

- Supabase 또는 PostgreSQL에 case/review/audit log 저장
- RAG corpus는 object storage 또는 별도 retrieval service로 분리
- 운영용 vector DB/semantic rerank 도입
- 개인정보 마스킹/저장 정책 강화
- 실제 금융기관 API 연동 시 읽기/쓰기 권한 분리

## 10. 알려진 한계

- 실제 금융회사 데이터 연동 없음
- mock 고객은 기본적으로 `CUST-001`
- 분쟁조정/판례 사례 수가 아직 작음
- retrieval은 개선됐지만 최종 판단 정확도는 별도 평가 필요
- 개인정보 처리와 운영 감사 로그는 production 수준 추가 구현 필요
- UI 데모와 실제 API 앱은 역할이 다름

## 11. 발표용 핵심 문장

> KB Key Buddy의 핵심은 RAG 검색 자체가 아니라, 검색된 근거를 금융 도메인에 맞게 분류하고 결론을 제한하는 안전한 판단 파이프라인입니다. 약관과 규정은 직접 근거로, 사례는 참고로, 절차 문서는 다음 행동 안내로 분리하며, 근거가 부족하면 자동 결론 대신 추가 질문이나 사람 검토로 전환합니다.
