# 구현 히스토리

이 문서는 KB Key Buddy가 현재 구조로 정리된 이유와 주요 시행착오를 기록합니다.

## 1. 복합 민원 분리 방식

초기에는 상품별로 별도 agent를 두는 구조를 검토했습니다. 하지만 실제 민원은 상품보다 “쟁점”이 먼저 드러나는 경우가 많아, 현재는 Case Builder가 민원을 이슈 단위로 분리하고 각 이슈에 product, issue_type, focal, required_facts를 붙이는 구조로 정리했습니다.

현재 구조:

```text
Case Builder
  -> issue splitting
  -> focal building
  -> required facts
  -> product / issue_type mapping
```

## 2. Mock Bank와 Finance MCP

실제 은행 API 연동은 MVP 범위에서 제외했습니다. 대신 mock 고객 `CUST-001`의 예금, 적금, 대출 계약과 거래/금리/안내 이력을 SQLite에 두고, Finance MCP 또는 in-process resolver가 읽기 전용으로 조회합니다.

중요한 수정:

- mock 데이터에서 생성되는 fact는 `USER_STATED`가 아니라 `SYSTEM_INFERRED`로 태깅하도록 변경했습니다.
- 사용자가 말한 사실과 시스템이 조회한 사실을 구분할 수 있게 됐습니다.

## 3. RAG Corpus 개선

초기 RAG는 약관/상품설명서 중심이었고, 사례와 절차 안내가 부족했습니다. 이후 다음 데이터를 보강했습니다.

- 법령/규정
- 상품설명서/약관
- 분쟁조정/판례 사례
- KB 민원 접수/처리 안내
- guides corpus

최근 주요 수정:

- `pypdf` 기본 추출에서 판례 PDF의 띄어쓰기가 사라지는 문제를 발견했습니다.
- `server/rag/ingest.py`에서 `extract_text(extraction_mode="layout")`로 변경했습니다.
- cases Recall@5가 87.5%에서 93.8%로 개선됐습니다.

## 4. Dedup과 Canonical 문서 정리

상품설명서와 약관에는 반복 문구가 많아 검색 결과 슬롯이 중복 문서로 낭비되는 문제가 있었습니다.

개선:

- 본문 정규화 기반 dedup
- canonical_doc_id mapping 일부 적용
- glossary는 판단 근거 검색에서 제외

## 5. Logic Audit Layer 도입

가장 중요한 구조 보강은 Evidence-Conclusion Audit Layer입니다.

이전 문제:

- 검색된 근거가 실제 결론을 지지하는지 별도로 검증하지 못했습니다.
- 분쟁조정 사례가 직접 결론처럼 표현될 위험이 있었습니다.

개선:

- `Fact.source_type` 추가
- `LogicVerification.support_chains[]` 추가
- `inference_type`: `direct_match`, `analogical`, `unverified`
- `evidence_role`: `direct_evidence`, `precedent_reference`, `procedure_guide`, `unknown`
- 근거 없음 또는 유사 사례-only 상태가 `proceed`로 나가지 않도록 Decision Gate에 반영

## 6. Decision Gate 재정의

`proceed`의 의미를 “결론 확정”이 아니라 “확인된 사실과 직접 근거 범위 안에서 다음 단계 안내 가능”으로 제한했습니다.

현재 상태:

| 상태 | 의미 |
| --- | --- |
| `proceed` | 직접 근거 범위 안에서 다음 단계 안내 가능 |
| `ask` | 추가 사실 또는 직접 근거 필요 |
| `amend` | 입력/마스킹/표현 보완 필요 |
| `hold` | 자동 판단 중지, 사람 검토 필요 |

## 7. Report Composer 안전화

최종 리포트에서 다음 표현을 차단하거나 완화합니다.

- 배상 가능
- 배상액
- 은행 잘못
- 위법
- 책임 인정
- 반드시 지급

허용하는 표현은 다음 네 가지입니다.

- 확인된 사실 기준
- 추가 확인 필요
- 유사 사례 참고
- 다음 행동/절차 안내

## 8. 현재 평가 결과

- RAG 평가셋: 42문항
- 전체 Recall@5: 97.6% (41/42)
- cases Recall@5: 93.8% (15/16)
- products Recall@5: 100.0% (20/20)
- guides Recall@5: 100.0% (6/6)
- corpus 규모: 65,764 chunks
- 테스트 수: 75개

## 9. 남은 개선 방향

- Support Accuracy 지표 정식 도입
- 평가셋 확대
- semantic rerank 또는 vector DB 운영 구조 도입
- 개인정보 마스킹/저장 정책 강화
- 실제 client와 API 응답 동기화
- 외부 기관 안내 데이터 추가 확충
