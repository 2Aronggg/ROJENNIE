# TODO

## 협업 규칙

두 사람은 같은 파일을 수정하지 않는다. 각자 브랜치를 따로 만들고, `main`에 직접 push하지 않는다.

| 담당 | 소유 파일 | 책임 |
|---|---|---|
| A: 데이터·서버 | `data/`, `server/`, `docs/todo/A_DATA_SERVER.md` | 문서 인덱싱, RAG, 공통 schema, API, 사실 검증 |
| B: 에이전트·클라이언트 | `agent/`, `client/`, `docs/todo/B_AGENT_CLIENT.md` | 에이전트 규칙, 결정 게이트, 답변, UI |
| 통합 담당 | `README.md`, `docs/PRD.md`, `docs/TODO.md` | 초기 구조 반영과 최종 통합만 담당 |

### Git 규칙

```text
A: feat/data-server
B: feat/agent-client
```

- A와 B는 각자 담당 디렉터리만 수정한다.
- `README.md`, `docs/PRD.md`, `docs/TODO.md`는 작업 중 수정하지 않는다.
- API 입력·출력 계약은 A가 먼저 정의하고 B는 읽기만 한다.
- 계약 변경이 필요하면 먼저 이슈나 PR 댓글로 합의한 뒤 통합 담당이 반영한다.
- 각자 브랜치를 push하고 별도 PR을 만든다. 한 브랜치에 공동 push하지 않는다.
- 통합 순서는 `A PR → API 계약 확인 → B PR`로 한다.

## 담당별 작업

- [A 데이터·서버 TODO](todo/A_DATA_SERVER.md)
- [B 에이전트·클라이언트 TODO](todo/B_AGENT_CLIENT.md)

## 통합 시점 체크리스트

통합 담당만 체크한다.

- [ ] A의 API schema와 B의 client 요청 형식이 일치함
- [ ] `proceed / amend / ask / hold` 값이 모든 계층에서 동일함
- [ ] 민원별 `issue_id`가 검색·검증·답변까지 유지됨
- [ ] 근거 문서의 `doc_id`, 페이지·섹션이 최종 답변에 연결됨
- [ ] 복합 민원 결과가 서로 섞이지 않음
- [ ] `complex_issue_75.json`으로 end-to-end 테스트 통과
- [ ] 개인정보 원문이 기본 답변에 노출되지 않음

## 데이터 수집 시점

현재 데이터로 MVP 구현과 분해·검색 파이프라인 검증을 먼저 진행한다. 공식 분쟁조정 사례, 절차·제출서류, 보험 문서는 MVP 평가 후 필요성이 확인될 때 추가한다.

## 완료 기준

- [ ] 복합 75건에서 하위 민원 수·상품·쟁점을 비교할 수 있음
- [ ] 답변마다 근거 문서와 적용 시점이 표시됨
- [ ] 핵심 사실이 없으면 자동으로 질문하거나 보류함
- [ ] 개인정보가 포함된 원문을 기본 답변에 그대로 노출하지 않음
- [ ] 현재 데이터 범위 밖의 상품·사례를 과장하지 않음
