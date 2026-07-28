# Server

금융 문의 분석, 문서 검색, 규정 검증, 답변 조합을 담당하는 영역입니다.

## 최소 모듈

```text
server/
├─ app.py            FastAPI endpoint
├─ schemas.py        Pydantic 입력·출력 모델
├─ ingest.py         PDF 텍스트 추출·chunk 생성
├─ retrieval.py      키워드 기반 최소 검색
├─ facts.py          사실 최신성·충돌 검증
└─ evaluation.py     자체 민원 평가
```

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

## API

- `GET /health`
- `POST /api/v1/cases/analyze`
- `GET /api/v1/cases/{case_id}`

각 민원 결과에는 `issue_id`, `product`, `issue_type`, `focal`, `target`, `facts`, `missing_facts`, `evidence_refs`, `decision`, `content_scope`, `next_steps`를 포함합니다.

## 구현 원칙

- 규정·사례 검색 결과가 없으면 근거가 있다고 가장하지 않는다.
- 문서 시행일을 검증한다.
- LLM이 만든 사실과 원문에서 추출한 사실을 구분한다.
- 외부 제출은 사용자 확인 없이는 실행하지 않는다.
- LangGraph, pgvector, reranker는 필요성이 확인된 뒤 추가한다.

## 로컬 실행

```powershell
python -m unittest server.test_p0
python -m server.ingest --data-dir data --output server/chunks.jsonl
python -m uvicorn server.app:app --reload
```

`server/chunks.jsonl`은 생성 산출물이므로 커밋하지 않습니다.