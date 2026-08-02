# 기술 평가 문서

이 문서는 KB Key Buddy(ROJENNIE)의 기술 평가 항목을 코드 경로, 데이터 수치, 평가 결과 중심으로 정리합니다. UI 시연 화면이 아니라 백엔드 분석 파이프라인, RAG, 안전성 검증 체계를 기준으로 작성했습니다.

## 문서 상태

- RAG 평가셋: 42문항
- 전체 Recall@5: 97.6% (41/42)
- 사례 문서 Recall@5: 93.8% (15/16)
- 상품 문서 Recall@5: 100.0% (20/20)
- 가이드 문서 Recall@5: 100.0% (6/6)
- corpus 규모: 65,764 chunks
- 테스트 수: 75개
- guides corpus 신설 반영
- Evidence-Conclusion Audit Layer 도입 반영

## 1. 데이터 적절성

### 1-1. 데이터 출처

| 데이터 종류 | 위치 | 역할 |
| --- | --- | --- |
| 법령/규정 | `data/regulations`, `data/corpus/regulations.jsonl` | 직접 판단 근거 |
| 상품설명서/약관 | `data/products`, `data/corpus/products.jsonl` | 상품 조건, 금리, 수수료 등 직접 근거 |
| 분쟁조정/판례 사례 | `data/cases`, `data/corpus/cases.jsonl` | 유사 사례 참고 |
| 절차 안내 | `data/guides`, `data/corpus/guides.jsonl` | 민원 접수, 분쟁조정, 반환지원 등 다음 행동 안내 |
| 평가셋 | `data/evaluation` | 검색/파이프라인 품질 검증 |
| mock 금융 데이터 | `server/finance/mock_bank.sqlite3`, `server/finance/mock_data.py` | 고객 계약·거래·금리·안내 이력 조회 시뮬레이션 |

운영 원칙:

- 약관/상품설명서/규정은 직접 근거로 사용합니다.
- 분쟁조정 사례와 판례는 유사 사례 참고로만 사용합니다.
- 절차 안내 문서는 다음 행동 안내에만 사용하고, 사실 판단 근거로 사용하지 않습니다.
- 데모 HTML과 평가셋은 실제 고객 데이터가 아니라 시연/검증용 데이터입니다.

### 1-2. Corpus 및 Chunking

현재 corpus는 총 65,764 chunks입니다. 문서 유형별로 chunking 기준을 달리합니다.

- 법령: 조문 단위 중심
- 상품설명서/약관: 페이지 및 섹션 단위
- 사례 문서: 사례 단위 보존
- 가이드 문서: 절차 항목 단위

최근 반영된 중요 수정:

| 문제 | 수정 |
| --- | --- |
| 판례 PDF 2개에서 pypdf 기본 추출 시 단어 사이 공백이 사라져 토큰 매칭 불가 | `server/rag/ingest.py`에서 `extract_text(extraction_mode="layout")` 적용 |
| 동일 약관/유사 문구가 여러 doc_id로 반복되어 근거 슬롯 낭비 | canonical doc_id 및 본문 정규화 기반 dedup 적용 |
| 가이드성 문서가 RAG 대상에 충분히 반영되지 않음 | guides corpus 신설 및 검색 평가셋에 guides 6문항 추가 |
| 용어사전이 판단 근거 검색에 섞일 위험 | glossary는 결정 검색에서 제외하고 별도 표시/설명 데이터로 분리 |

## 2. 검색/RAG 성능

평가 스크립트:

```powershell
python -m server.tests.evaluate_retrieval
```

최종 평가 결과:

| 구분 | Recall@5 |
| --- | --- |
| cases | 15/16 = 93.8% |
| products | 20/20 = 100.0% |
| guides | 6/6 = 100.0% |
| 전체 | 41/42 = 97.6% |

현재 놓친 케이스:

```text
대출 만기 연장했더니 금리가 갑자기 너무 많이 올랐어요
정답 doc_id=01c1817ae095
```

해석:

- 상품 문서와 절차 안내 문서는 현재 평가셋에서 모두 top-5 안에 들어옵니다.
- 사례 문서는 PDF 추출 방식 개선 후 87.5%에서 93.8%로 개선됐습니다.
- 전체 평가는 42문항 기준 97.6%입니다.
- 검색 성공이 곧 판단 정확도를 뜻하지 않기 때문에, Logic Verification 단계에서 근거-결론 지지 여부를 별도로 검사합니다.

## 3. Evidence-Conclusion Audit Layer

가장 중요한 구조 보강은 “검색된 근거가 결론을 실제로 지지하는가”를 별도 검증하는 감사 레이어입니다.

관련 코드:

- `server/schemas.py`
- `server/agents/logic_verification.py`
- `server/agents/decision_gate.py`
- `server/agents/report_composer.py`
- `server/tests/test_logic_audit.py`

### 3-1. Fact 출처 태깅

모든 fact는 다음 중 하나의 출처를 가져야 합니다.

| Source Type | 의미 |
| --- | --- |
| `USER_STATED` | 사용자가 직접 말한 사실 |
| `SYSTEM_INFERRED` | 시스템이 mock 금융 데이터나 규칙으로 확인/추론한 사실 |
| `DOCUMENT_EVIDENCE` | 문서에서 확인된 근거 |
| `PRECEDENT_REFERENCE` | 분쟁조정 사례/판례 참고 |

최근 수정:

- `server/agents/facts.py`: 과거 `source_ref` 기반 소문자 source type 변환 제거, `fact.source_type` 직접 사용
- `server/agents/mock_customer_data_resolver.py`: 은행 mock 데이터 fact를 기본 `USER_STATED`가 아니라 `SYSTEM_INFERRED`로 생성

### 3-2. Support Chain

`LogicVerification.support_chains[]`는 다음 구조를 기록합니다.

```text
claim
  -> supporting_evidence[]
  -> inference_type
  -> evidence_role
  -> allowed_in_final
```

`inference_type`:

- `direct_match`: 약관/규정/상품설명서 등 직접 근거
- `analogical`: 유사 사례 기반 참고
- `unverified`: 근거 부족

`evidence_role`:

- `direct_evidence`
- `precedent_reference`
- `procedure_guide`
- `unknown`

## 4. Decision Gate 기준 변경

기존 Decision Gate는 주로 missing facts, high-risk issue, PII, routing confidence를 기준으로 `proceed/ask/amend/hold`를 정했습니다.

감사 레이어 도입 후 변경된 기준:

| 상황 | 처리 |
| --- | --- |
| 직접 근거 없음 + `proceed` | `ask`로 강등 |
| 유사 사례만 있음 + `proceed` | `ask`로 강등 |
| `unverified` claim 존재 | `unsupported_claim` / `unverified_claim` risk flag 기록 |
| 직접 약관/규정/상품설명서 근거 있음 | 다른 위험이 없으면 제한된 `proceed` 가능 |
| 판례/분쟁사례 참고 | “유사 사례에서는” 수준으로만 표현, 결론 직접 인용 금지 |

상태 의미:

| 상태 | 의미 |
| --- | --- |
| `proceed` | 확인된 사실과 직접 근거 범위 안에서 다음 단계 안내 가능 |
| `ask` | 추가 사실 또는 직접 근거 필요 |
| `amend` | 마스킹/입력 보완/표현 범위 조정 필요 |
| `hold` | 자동 판단 중지, 사람 검토 필요 |

중요: `proceed`는 “은행 잘못 확정”, “배상 가능 확정”이 아니라 “확인된 범위 안에서 다음 단계 안내 가능”이라는 의미입니다.

## 5. Report Composer 안전장치

`server/agents/report_composer.py`는 최종 리포트에서 단정 표현을 제한합니다.

차단/완화 대상 표현:

- 배상 가능
- 배상액
- 보상받을 수 있음
- 은행 잘못
- 위법
- 책임 인정
- 반드시 지급

허용 표현 범위:

- 확인된 사실 기준
- 추가 확인 필요
- 유사 사례 참고
- 접수/분쟁조정/반환지원 등 다음 행동 안내

## 6. 테스트 및 검증

현재 테스트 수는 75개입니다.

대표 검증:

| 테스트 | 결과 |
| --- | --- |
| `server/tests/test_facts.py` | 3 passed |
| `server/tests/test_logic_audit.py` | 3 passed |
| retrieval 전체 평가 | 41/42 = 97.6% |

`test_logic_audit.py`가 검증하는 내용:

- 근거 없음 + `proceed`는 `ask`로 강등
- 유사 사례만 있음 + `proceed`는 `ask`로 강등
- 직접 상품/규정 근거가 있으면 다른 위험이 없을 때 `proceed` 유지 가능

## 7. 현재 한계

- 실제 금융기관 API 연동은 아직 아니며, mock SQLite 기반입니다.
- RAG는 로컬 corpus 기반 검색이며, 운영용 벡터 DB/semantic rerank는 추가 개선 영역입니다.
- 분쟁조정 사례/판례 수는 아직 충분하지 않습니다.
- 개인정보 마스킹과 저장 정책은 production 수준으로 추가 구현해야 합니다.
- 검색 Recall은 높아졌지만, 최종 판단 정확도는 별도 Support Accuracy 지표로 계속 검증해야 합니다.

## 8. 발표용 핵심 문장

> KB Key Buddy는 검색 결과를 곧바로 결론으로 쓰지 않습니다. 약관·규정·상품설명서는 직접 근거로, 분쟁조정 사례는 유사 사례 참고로, 민원 절차 문서는 다음 행동 안내로 분리합니다. 이후 Logic Verification과 Decision Gate가 근거 없는 결론을 `ask` 또는 `hold`로 막아 금융 민원 도메인에서 안전한 분석 흐름을 제공합니다.
