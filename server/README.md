# Server

금융 문의 분석, 문서 검색, 규정 검증, 답변 조합을 담당하는 영역입니다.

## 최소 모듈

```text
server/
├─ api/              FastAPI endpoint
├─ schemas/          Pydantic 입력·출력 모델
├─ agents/           5개 에이전트 호출부
├─ retrieval/        PDF chunk, keyword/vector 검색
├─ case_graph/       사건·사실·증빙 관계
├─ policy/           Decision Gate, Content Scope
└─ evaluation/       자체 민원 평가·회귀 테스트
```

실제 구현 시 이 구조를 그대로 만들 필요는 없습니다. 한 파일에 먼저 동작을 만들고, 모듈 분리는 코드가 커질 때 진행합니다.

## 처리 순서

```text
request
→ validate input
→ split issues
→ build focal/evidence
→ resolve facts
→ retrieve evidence
→ verify logic
→ decision gate
→ compose response
```

## API 응답 필수값

각 민원 결과에는 최소한 다음을 포함합니다.

- `issue_id`
- `product`
- `issue_type`
- `focal`
- `target`
- `facts`
- `missing_facts`
- `evidence_refs`
- `decision.control`
- `decision.risk_flags`
- `content_scope`
- `next_steps`

## 구현 원칙

- 규정·사례 검색 결과가 없으면 근거가 있다고 가장하지 않는다.
- 문서 시행일을 검증한다.
- LLM이 만든 사실과 원문에서 추출한 사실을 구분한다.
- 외부 제출은 사용자 확인 없이는 실행하지 않는다.
- LangGraph, pgvector, reranker는 필요성이 확인된 뒤 추가한다.
