# TODO

앞으로 할 일만 적는다. 완료된 작업 이력은 git log에 있으므로 여기 남기지 않는다.

## 지금 하는 것

- [ ] **두 브랜치를 main으로 합치기.** `feat/data-server`(8커밋)와 `feat/agent-client`(2커밋)가
      `main` 기준으로 각자 앞서 있고, 두 브랜치가 `retrieval.py`에서 형태소 분석을 서로 다르게
      구현해 충돌이 예약돼 있다. 합친 뒤에는 main에서 작업한다.
  - 형태소 분석 **구조는 data-server 쪽** 채택: 전체 청크를 corpus 빌드 시점에 토큰화해
    `DocumentChunk.tokens`로 캐싱, 인덱스·IDF 전부 형태소 기반. agent-client 쪽(정규식 인덱스
    유지 + 일부 청크만 stems 부스트)은 규정 문서에 조사 문제가 그대로 남는다.
  - 형태소 **품사 세트는 agent-client 쪽** 흡수: VV(동사 어간)/VA(형용사 어간)/XR/SH를 추가해
    "올랐어요→오르" 같은 활용형도 매칭.
  - 단 agent-client의 **2글자 미만 필터는 숫자(SN)에 적용하지 않는다** — "스타적금3"의 "3"이
    사라져 상품명 구분 신호가 깨진다.
  - 그 외: 컴플라이언스 레이어·facts source_type·라우터 previous_product 승계·Decision Gate
    기대값은 agent-client 쪽, 지원상품아님 조기거절·상품명 section 신호는 data-server 쪽 유지.
- [ ] 머지 후 재측정: retrieval 42문항, Decision Gate 6시나리오, 리포트 grounding 5건, 전체 테스트.

## 응답 속도 (현재 12~20초)

- [ ] **`rag_query` LLM 단계 제거 검토.** 측정 결과 LLM 검색어가 원문·규칙보다 오히려 나빴다
      (사례 8건: 원문 8/8, 규칙 8/8, LLM 6/8) — 이슈당 2초를 쓰고 품질이 떨어진다. 42문항
      전체로 재확인한 뒤 규칙 기반으로 고정하거나 단계 자체를 뺀다.
- [ ] 라우팅(`issue_splitter`)은 LLM 유지. 실데이터 기준 LLM 91.4% vs 규칙 65.5%로 격차가 크고,
      첫 단계라 여기서 틀리면 이후가 전부 오염된다. (`server/tests/evaluate_aihub.py`)

## 배포 (Vercel + Supabase)

- [ ] 만료 법령을 corpus에서 제외한 뒤 인덱스 로딩 시간·메모리 재측정. 기존 95초/GB 단위가
      서버리스 배포를 막던 원인이었다.
- [ ] 위 결과에 따라 pgvector 사용 여부 결정. corpus가 충분히 작아지면 `SUPABASE_RAG_ENABLED`
      없이 인메모리로 배포할 수 있고, 그러면 pgvector 경로를 유지할 이유가 사라진다.
- [ ] pgvector를 계속 쓴다면 배포 전 42문항을 **pgvector 경로로** 재측정할 것. SQL
      (`match_rag_chunks`)은 순수 벡터 유사도만 쓰고 로컬의 텍스트 점수·상품명 가중치·intent
      보정이 없어서, 문서에 적힌 recall 수치가 배포 환경을 설명하지 못한다.

## 시연 품질

- [ ] **`notice_history`가 0건이다.** 대표 민원이 "금리 인상 안내를 못 받았다"인데 안내 이력
      테이블이 비어 있어 "안내 기록 없음"을 근거로 제시할 수 없다. `transactions`도 3건뿐.
      고객 수를 늘리기 전에 한 명(CUST-001)의 이력부터 두껍게 채운다.
- [ ] 대조군 고객 1명 추가(CUST-002 = 안내를 제대로 받은 고객). 같은 질문에 다른 답이 나오는
      시연이 "내 금융정보와 대조한다"는 차별점을 가장 직접적으로 보여준다.

## 정리

- [ ] 데모 HTML 중복 통합: `demo/agent2~4`는 정적판과 라이브판이 `agent-api.js` 로드 2줄만
      다르고 agent1은 레이아웃이 252줄 갈라졌다. `agent-api.js` 유무로 동작을 나눠 파일 하나로
      합친다. (agent-client 브랜치가 같은 파일을 수정 중이라 머지 이후)
- [ ] 사용되지 않는 엔드포인트 제거: `/api/v1/cases/{id}/review`, `/api/v1/cases/{id}/audit`,
      `/mock/accounts/*` 4개, `/mock/customers/{id}/products`. 클라이언트도 MCP도 호출하지 않는다.

## 유지하기로 한 것 (재론 방지)

- **관리자 페이지**: 민원 유입량과 에이전트별 fallback 발생률 모니터링이 목적. 자기 시스템이
  언제 LLM 대신 규칙으로 떨어지는지 감시한다는 점에서 유지 가치가 있다.
- **Finance MCP 레이어**: in-process 기본 transport라 코드 층이 한 겹 늘지만, `stdio` 모드로
  실제 MCP 프로토콜을 쓸 수 있게 설계돼 있고 AI 챌린지 맥락에서 의미가 있다.

## 협업 규칙

- main에서 작업한다. 브랜치를 나눌 경우 **작업 시작 전에 상대 브랜치를 먼저 pull한다** —
  같은 문제(형태소 분석)를 각자 따로 구현하는 일이 두 번 발생했다.
- `data/` 하위에 대용량 파일을 추가할 때는 gitignore 대상인지 먼저 확인한다. GitHub 100MB
  한도를 넘겨 푸시가 거부된 적이 있다(`server/rag/chunks.jsonl`).
- 실제 고객정보·실제 계좌번호·주민번호는 수집하지 않는다.
