# Server

KB Key Buddy 서버는 FastAPI 기반의 금융 민원 분석 파이프라인입니다. 사용자의 복합 민원을 이슈 단위로 분리하고, mock 금융 데이터와 RAG 문서 근거를 함께 확인한 뒤 안전한 응답과 다음 행동을 구성합니다.

현재 서버는 실제 은행 내부망이나 실고객 데이터에 연결되어 있지 않습니다. 금융 데이터는 `server/finance/mock_bank.sqlite3`와 `server/finance/mock_data.py` 기반의 시연용 mock 데이터입니다.

## API

| Method | Path | 역할 |
| --- | --- | --- |
| `POST` | `/api/v1/cases/analyze` | 민원 입력을 분석하고 case/issues/report 구조를 생성 |
| `GET` | `/api/v1/cases/{case_id}` | 저장된 case 분석 결과 조회 |
| `POST` | `/api/v1/cases/{case_id}/review` | 사람 검토 결과를 case에 반영 |

## 처리 흐름

```text
POST /api/v1/cases/analyze
  -> Case Builder
     - issue splitting
     - focal/target/required facts 구성
  -> Mock Customer Data Resolver / Finance MCP
     - 고객, 상품, 거래, 금리, 안내 이력 조회
  -> RAG Query + Retrieval
     - 약관, 상품설명서, 규정, 사례, 절차 안내 검색
  -> Logic Verification
     - fact source와 evidence role 분리
     - claim-support chain 생성
  -> Decision Gate
     - proceed / ask / amend / hold 결정
  -> Report Composer
     - 단정 표현을 제한한 사용자용 리포트 생성
```

## 주요 모듈

| 경로 | 역할 |
| --- | --- |
| `server/app.py` | FastAPI 엔드포인트와 전체 파이프라인 오케스트레이션 |
| `server/schemas.py` | case, issue, fact, evidence, decision, report 스키마 |
| `server/agents/router.py` | 민원 product/issue_type 라우팅 |
| `server/agents/focal_builder.py` | 이슈별 확인 지점과 필수 사실 구성 |
| `server/agents/facts.py` | fact 충돌, 최신값, provenance 정리 |
| `server/agents/mock_customer_data_resolver.py` | mock bank 데이터를 fact로 변환 |
| `server/agents/rag_query.py` | RAG 검색 쿼리 생성 |
| `server/rag/retrieval.py` | 로컬 corpus 검색, 필터, dedup, rerank |
| `server/agents/logic_verification.py` | 근거-결론 지지 검증 |
| `server/agents/decision_gate.py` | 비LLM 정책 기반 최종 상태 결정 |
| `server/agents/report_composer.py` | issue별 안전 리포트 생성 |
| `server/policy/gateway.py` | LLM 호출 전후 정책 게이트, PII 마스킹, 금지 표현 필터 |

## 수동 실행 스크립트 (`server/scripts/`)

서버가 부르지 않고 사람이 필요할 때 직접 돌리는 도구입니다. 데이터를 새로 넣거나 검색 품질을 확인할 때만 쓰면 되고, 평소 실행에는 필요 없습니다.

| 스크립트 | 언제 쓰나 | 결과 |
|---|---|---|
| `fetch_law_data.py` | 법령 원문을 새로 받을 때 | 국가법령정보센터 API → `data/regulations/law_api/*.json` |
| `extract_cases.py` | 분쟁조정 사례 HWP/HWPX를 받았을 때 | 본문 추출 + 내용 기반 상품 분류 → `data/cases/cases.csv` |
| `crawl_kca_cases.py` | 한국소비자원 분쟁조정 사례를 수집할 때 | → `data/cases/kca_cases.jsonl` |
| `crawl_fss_decisions.py` | 금융감독원 분쟁조정 결정을 수집할 때 | → `data/cases/fss_decisions.jsonl` |
| `merge_complaints.py` | AIHub 상담 데이터의 원문·라벨 JSON을 합칠 때 | → `data/complaints/**/complaints.jsonl` |
| `report_retrieval_failures.py` | 검색 평가에서 놓친 건의 원인을 볼 때 | 질의별 상위 결과와 정답 문서 순위를 출력 |
| `evaluate_service_pipeline.py` | UI 없이 파이프라인 전체를 한 번에 돌려볼 때 | 시나리오별 상태·근거 요약 출력 |

크롤러는 대상 사이트를 그대로 긁어오므로 상품 분류가 느슨할 수 있습니다. 실제로 한국소비자원 수집분 33건 중 17건이 보험·상조·카드 사례였고, 원본을 고치는 대신 `status`를 `out_of_scope`로 표시해 corpus 빌드에서 빠지게 했습니다. 새로 수집할 때도 그대로 넣지 말고 건별로 확인해야 합니다.

수집·추출 후에는 corpus를 다시 만들어야 반영됩니다(루트 `README.md`의 재빌드 절차 참고).

## Finance MCP / Mock Bank

Finance MCP는 실제 금융회사 API가 아니라, mock bank 데이터를 읽기 전용 tool 형태로 노출하는 연결 계층입니다.

대표 기능:

- `get_my_profile`
- `get_my_products`
- `get_my_deposits`
- `get_my_savings`
- `get_my_loans`
- `get_my_transactions`
- `get_my_repayments`
- `get_my_rate_history`
- `get_my_notice_history`
- `calculate_interest`

운영 원칙:

- 고객 ID는 LLM이나 사용자가 임의로 지정하지 않습니다.
- 현재 세션은 기본 mock 고객 `CUST-001`에 연결됩니다.
- 조회와 계산만 수행하며, 계좌 변경/이체/민원 자동 제출 같은 쓰기 작업은 없습니다.
- mock 데이터에서 읽은 fact는 `SYSTEM_INFERRED`로 태깅합니다.

## RAG Corpus

RAG는 `data/`와 `data/corpus/`의 로컬 문서를 기반으로 합니다.

| 문서 유형 | 용도 |
| --- | --- |
| 규정/법령 | 직접 근거 |
| 상품설명서/약관 | 직접 근거 |
| 분쟁조정/판례 사례 | 유사 사례 참고 |
| 절차 안내 가이드 | 민원 접수, 분쟁조정, 반환지원 등 다음 행동 안내 |
| 용어사전 | 사용자 표시/설명용, 판단 근거 검색에서는 제외 |

현재 retrieval 평가:

- 평가셋: 42문항
- 전체 Recall@5: 100.0% (42/42)
- cases: 100.0% (16/16)
- products: 100.0% (20/20)
- guides: 100.0% (6/6)
- corpus 규모: 65,764 chunks

## Logic Audit

검색 결과가 있다고 해서 바로 결론으로 사용하지 않습니다. Logic Verification은 각 claim에 대해 support chain을 만듭니다.

```text
claim
  -> supporting_evidence[]
  -> inference_type: direct_match | analogical | unverified
  -> evidence_role: direct_evidence | precedent_reference | procedure_guide | unknown
```

Decision Gate 기준:

- 직접 근거 없음 + `proceed`는 `ask`로 강등
- 유사 사례만 있음 + `proceed`는 `ask`로 강등
- `unverified` claim은 `unsupported_claim` / `unverified_claim` risk flag로 기록
- 약관/규정/상품설명서 직접 근거가 있으면 다른 위험이 없을 때 제한된 `proceed` 가능

## 상태 의미

| 상태 | 의미 |
| --- | --- |
| `proceed` | 확인된 사실과 직접 근거 범위에서 다음 단계 안내 가능 |
| `ask` | 추가 사실 또는 직접 근거 필요 |
| `amend` | 마스킹, 입력 보완, 표현 범위 조정 필요 |
| `hold` | 자동 판단 중지, 사람 검토 필요 |

`proceed`는 법적 책임, 배상 가능성, 은행 과실을 확정한다는 뜻이 아닙니다.

## 로컬 실행

```powershell
cd C:\Users\achim\ROJENNIE
python -m pip install -r server\requirements.txt
python -m uvicorn server.app:app --reload
```

RAG corpus 재생성:

```powershell
python -m server.rag.ingest --data-dir data --output server/rag/chunks.jsonl
python -m server.rag.build_corpus --data-dir data --chunks server/rag/chunks.jsonl --output-dir data/corpus
```

retrieval 평가:

```powershell
python -m server.tests.evaluate_retrieval
```

## LLM 사용

`GEMINI_API_KEY`가 있으면 일부 단계에서 Gemini 기반 JSON 생성을 사용할 수 있습니다. LLM 호출은 항상 `server/policy/gateway.py`를 통과합니다.

정책:

- PII 마스킹
- 허용 stage 확인
- JSON schema 검증
- 금지 표현 필터
- 실패 시 deterministic fallback 사용

LLM은 고객 ID, 거래 사실, 계산 결과를 임의 생성하면 안 됩니다. 최종 상태 결정은 Decision Gate가 담당합니다.

## 명시적 제외 범위

- 실제 은행 내부 시스템 연동
- 실제 고객 개인정보 저장
- 계좌/계약 변경, 이체, 민원 자동 제출
- 배상 가능성, 과실, 위법 여부 확정
- 운영용 벡터 DB 또는 production-grade 개인정보 처리
