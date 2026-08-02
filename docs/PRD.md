# PRD: KB Key Buddy 금융소비자 민원 분석 기능

문서 기준: 2026-08-02
상태: MVP / 제출용 프로토타입 기준

## 1. 제품 개요

KB Key Buddy는 사용자가 입력한 복합 금융 민원을 이슈 단위로 분리하고, 확인된 금융 정보와 문서 근거를 바탕으로 다음 행동을 안내하는 금융소비자 보호 서비스입니다.

현재 MVP는 다음 범위를 지원합니다.

- 예금
- 적금
- 대출

서비스는 금융회사 과실, 배상 가능성, 위법 여부를 자동 확정하지 않습니다. 확인된 사실과 직접 근거가 부족한 경우에는 `ask` 또는 `hold`로 안전하게 멈춥니다.

## 2. 문제 정의

금융 민원은 보통 하나의 문장 안에 여러 문제가 섞여 있습니다.

예:

```text
예금 만기 이자가 예상보다 적게 들어왔고,
적금 우대금리도 적용되지 않았는데,
은행에서 안내를 제대로 받지 못한 것 같습니다.
```

사용자는 다음을 한 번에 알고 싶어 합니다.

- 내 민원이 몇 개 문제로 나뉘는지
- 어떤 상품/거래/약관을 확인해야 하는지
- 지금 추가로 답해야 할 정보가 무엇인지
- 어떤 근거 문서를 봐야 하는지
- 지금 바로 진행 가능한지, 사람 검토가 필요한지
- 다음 행동은 무엇인지

## 3. 목표

### 사용자 목표

- 복합 민원을 카드 단위로 이해한다.
- 예금/적금/대출 이슈를 분리해서 확인한다.
- 사용자가 이미 말한 사실을 다시 묻지 않는다.
- 부족한 사실만 친절하게 질문받는다.
- 약관, 상품설명서, 사례, 절차 안내를 한곳에서 본다.
- 단정적인 법률 판단이 아니라 안전한 다음 행동을 받는다.

### 시스템 목표

- 민원 원문을 구조화된 `case/issues`로 변환한다.
- fact의 출처를 구분한다.
- RAG 검색 결과와 최종 판단을 분리한다.
- 직접 근거, 유사 사례, 절차 안내를 구분한다.
- 근거 없는 결론이 `proceed`로 나가지 않도록 차단한다.
- LLM이 실패해도 fallback으로 응답 가능해야 한다.

## 4. 비목표

다음은 현재 MVP 범위가 아닙니다.

- 실제 은행 내부 시스템 연동
- 실제 고객 계좌 조회
- 계좌 변경, 이체, 해지, 민원 자동 제출
- 배상 가능성/은행 과실/위법 여부 확정
- 신용평가 또는 대출 승인 판단
- 실고객 개인정보 저장
- production-grade vector DB 운영

## 5. 사용자 흐름

### 5-1. 민원 입력

사용자는 자연어로 복합 민원을 입력합니다.

요구사항:

- 긴 문장, 감정 섞인 표현, 여러 상품이 섞인 입력을 허용한다.
- 입력된 원문은 `USER_STATED` fact의 출처가 된다.
- 시스템은 원문을 임의로 축약해 사실을 바꾸면 안 된다.

### 5-2. 이슈 분리

Case Builder가 민원을 여러 이슈로 분리합니다.

예:

```text
복합 민원
  -> 예금 만기 이자 불일치
  -> 적금 우대금리 미적용
```

요구사항:

- issue_id를 부여한다.
- product와 issue_type을 기록한다.
- 필요한 확인 항목을 `required_facts`로 기록한다.
- 분리 확신이 낮으면 `ask` 또는 사람 검토 대상으로 보낸다.

### 5-3. 금융 정보 확인

Mock Customer Data Resolver / Finance MCP가 mock 금융 데이터를 조회합니다.

요구사항:

- 현재 MVP는 mock 고객 `CUST-001`만 사용한다.
- 조회된 fact는 `SYSTEM_INFERRED`로 기록한다.
- 사용자가 말한 사실과 mock 데이터가 충돌하면 conflict로 기록한다.
- 실제 은행 API 또는 실고객 데이터라고 표현하지 않는다.

### 5-4. RAG 근거 검색

RAG는 issue별로 필요한 문서를 검색합니다.

문서 역할:

| 문서 | 역할 |
| --- | --- |
| 약관/상품설명서/규정 | 직접 근거 |
| 분쟁조정 사례/판례 | 유사 사례 참고 |
| 민원/분쟁 절차 안내 | 다음 행동 안내 |
| 용어사전 | 설명/표시용 |

요구사항:

- 검색 결과는 EvidenceRef로 반환한다.
- doc_id, chunk_id, path, page, snippet, score를 포함한다.
- 유사 사례는 직접 결론 근거로 쓰지 않는다.

### 5-5. 논리 검증

Logic Verification은 근거가 결론을 실제로 지지하는지 확인합니다.

요구사항:

- 각 claim에 support chain을 만든다.
- inference_type을 기록한다.
- direct evidence가 없으면 최종 결론으로 내보내지 않는다.
- analogical claim은 “유사 사례 참고”로만 표현한다.

### 5-6. Decision Gate

Decision Gate는 최종 상태를 결정합니다.

| 상태 | 조건 |
| --- | --- |
| `proceed` | 확인된 사실과 직접 근거 범위 안에서 다음 단계 안내 가능 |
| `ask` | 금액, 날짜, 안내 내용, 거래내역 등 추가 정보 필요 |
| `amend` | 개인정보 마스킹, 입력 보완, 표현 범위 조정 필요 |
| `hold` | 고위험, 사실 충돌, 근거 부족, 사람 검토 필요 |

요구사항:

- `proceed`는 결론 확정이 아니다.
- 근거 없음 + proceed는 ask로 강등한다.
- 유사 사례만 있음 + proceed는 ask로 강등한다.
- 고위험 신호는 hold로 보낸다.

### 5-7. 리포트 생성

Report Composer는 사용자용 리포트를 구성합니다.

리포트 항목:

- 민원 내용
- 확인된 사실
- 처리 결과 또는 현재 상태
- 추가 확인 필요 항목
- 근거 문서
- 소비자 유의사항
- 다음 행동

금지 표현:

- 배상 가능 확정
- 은행 잘못 확정
- 위법 확정
- 책임 인정
- 반드시 지급

허용 표현:

- 확인된 사실 기준
- 추가 확인 필요
- 유사 사례 참고
- 절차 안내

## 6. API 요구사항

### `POST /api/v1/cases/analyze`

입력:

```json
{
  "case_id": "optional",
  "session_id": "optional",
  "customer_id": "CUST-001",
  "prompt": "민원 원문",
  "as_of": "2026-08-02"
}
```

출력:

```json
{
  "case_id": "case_...",
  "prompt": "...",
  "issues": [
    {
      "issue_id": "issue_001",
      "product": "예금",
      "issue_type": "만기이자불일치",
      "facts": [],
      "missing_facts": [],
      "evidence_refs": [],
      "logic_verification": {},
      "decision": {
        "control": "ask",
        "risk_flags": []
      },
      "report": {}
    }
  ]
}
```

### `GET /api/v1/cases/{case_id}`

저장된 case 결과를 조회합니다.

### `POST /api/v1/cases/{case_id}/review`

사람 검토 결과를 반영합니다.

## 7. 데이터 요구사항

### Fact

모든 fact는 출처를 가져야 합니다.

| source_type | 의미 |
| --- | --- |
| `USER_STATED` | 사용자가 말한 사실 |
| `SYSTEM_INFERRED` | 시스템이 조회/추론한 사실 |
| `DOCUMENT_EVIDENCE` | 문서 근거 |
| `PRECEDENT_REFERENCE` | 유사 사례 참고 |

### Evidence

EvidenceRef는 최소 다음 값을 포함합니다.

- doc_id
- chunk_id
- path
- page
- snippet
- score
- match_type

## 8. 안전 요구사항

- LLM은 최종 상태를 단독 결정하지 않는다.
- 모든 LLM 호출은 Policy Gateway를 통과한다.
- 개인정보는 LLM 호출 전 마스킹해야 한다.
- 근거 없는 결론은 report에서 차단한다.
- 판례/분쟁조정 사례는 직접 인용형 결론으로 쓰지 않는다.
- `ask`와 `hold`는 시스템 실패가 아니라 안전장치로 표현한다.

## 9. 평가 기준

현재 기준:

- RAG 평가셋: 42문항
- 전체 Recall@5: 97.6%
- cases Recall@5: 93.8%
- products Recall@5: 100.0%
- guides Recall@5: 100.0%
- 테스트 수: 75개

추가로 계속 봐야 할 지표:

- issue split 정확도
- missing_facts 질문 적합도
- support accuracy
- unsafe proceed 차단율
- 사용자 다음 행동 안내 성공률

## 10. UI 요구사항

현재 UI는 두 종류로 나뉩니다.

### 실제 client 앱

- API 응답의 `case/issues/status/evidence/report`를 카드 UI로 렌더링하는 방향
- 실제 API 연동은 진행 중

### 시연용 HTML

- `flow.html`, agent demo HTML 등
- 발표용 단일 HTML 목업
- 실제 서버/API와 완전히 동기화된 앱은 아님
- 이미지/아이콘은 제공된 로제니 에셋을 사용

## 11. 성공 기준

MVP 성공 기준:

- 복합 민원을 2개 이상 이슈로 분리할 수 있다.
- 각 이슈에 필요한 fact와 missing_facts를 표시한다.
- RAG 근거를 top-5 안에서 안정적으로 찾는다.
- 직접 근거와 유사 사례를 구분한다.
- 근거 없는 결론이 proceed로 나가지 않는다.
- 사용자에게 안전한 다음 행동을 제시한다.

## 12. 로드맵

단기:

- 평가셋 확대
- Support Accuracy 측정
- missing_facts 질문 템플릿 개선
- 문서 canonical mapping 전수 정리

중기:

- semantic rerank 또는 vector DB 도입
- 실제 client API 연동
- 개인정보 마스킹 테스트 강화
- 기관별 절차 안내 데이터 확충

장기:

- 실제 금융기관 API 연동 검토
- 운영용 감사 로그/리뷰 큐 구축
- 상담원/심사역용 검토 화면 구축
