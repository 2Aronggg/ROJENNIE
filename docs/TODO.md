# TODO

앞으로 할 일만 적는다. 완료된 작업 이력은 git log에 있으므로 여기 남기지 않는다.

## 1. 브랜치 합치기 (먼저 해야 나머지가 안 꼬임)

- [ ] **`feat/data-server`와 `feat/agent-client`를 main으로 합치기.** 두 브랜치가 main 기준으로
      각자 앞서 있고 `retrieval.py`에서 형태소 분석을 서로 다르게 구현해 충돌이 예약돼 있다.
      합친 뒤에는 main에서 작업한다.
  - 형태소 분석 **구조는 data-server 쪽**: 전체 청크를 corpus 빌드 시점에 토큰화해
    `DocumentChunk.tokens`로 캐싱, 인덱스·IDF 전부 형태소 기반. agent-client 쪽(정규식 인덱스
    유지 + 일부 청크만 stems 부스트)은 규정 문서에 조사 문제가 그대로 남는다.
  - 형태소 **품사 세트는 agent-client 쪽 흡수**: VV(동사 어간)/VA(형용사 어간)/XR/SH를 추가해
    "올랐어요→오르" 같은 활용형도 매칭한다.
  - 단 agent-client의 **2글자 미만 필터를 숫자(SN)에는 적용하지 않는다** — "스타적금3"의 "3"이
    사라져 상품명 구분 신호가 깨진다.
  - 그 외: 컴플라이언스 레이어·facts source_type·라우터 previous_product 승계·Decision Gate
    기대값은 agent-client 쪽, 지원상품아님 조기거절·상품명 section 신호는 data-server 쪽.
- [ ] 머지 후 재측정: retrieval 42문항, Decision Gate 6시나리오, 리포트 grounding 5건, 전체 테스트.

## 2. 배포 (Vercel + Supabase) — 지금 상태로는 배포되지 않음

코드 쪽 준비는 끝났다. 남은 것은 실제 배포와 그 검증이다.

- [x] corpus를 배포 번들에 포함 — `.gitignore`가 `data/corpus/all.jsonl`만 예외로 추적한다
      (36.8MB, 서버가 읽는 유일한 corpus 파일). 나머지 per-corpus 파일은 중복이라 계속 제외.
- [x] Mock Bank의 읽기 전용 파일시스템 대응 — `MOCK_BANK_DB=:memory:`로 인메모리 SQLite를
      쓰고, 파일 쓰기가 실패하면 자동으로 인메모리로 넘어간다. 시드 데이터를 매번 상수에서
      다시 쓰기 때문에 파일이 없어도 동작이 같다.
- [x] `vercel.json` + `api/index.py` 진입점 추가. 번들 크기는 문제가 아니었다 — Fluid Compute는
      5GB까지 지원하고 현재 의존성은 약 214MB(kiwipiepy 모델 105MB 포함)다.
- [ ] **실제로 배포해서 확인한다.** 로컬에서 검증한 것은 진입점 import와 `/health`뿐이다.
      배포 후 `/api/v1/cases/analyze`가 실제 근거를 반환하는지, 콜드 스타트가 몇 초인지 잰다.
- [ ] Vercel 환경변수 설정: `GEMINI_API_KEY`, `MOCK_BANK_DB=:memory:`,
      `CORS_ORIGINS`(배포 도메인), 필요 시 `SUPABASE_URL`/`SUPABASE_SECRET_KEY`.
- [ ] 배포 후 pgvector 사용 여부 결정. corpus가 3,787청크/인덱스 6.2초까지 줄어서 인메모리로
      충분할 가능성이 높고, 그러면 pgvector 경로를 유지할 이유가 없다.
- [ ] pgvector를 계속 쓴다면 배포 전 42문항을 **pgvector 경로로** 재측정할 것. SQL
      (`match_rag_chunks`)은 순수 벡터 유사도만 쓰고 로컬의 텍스트 점수·상품명 가중치·intent
      보정이 없어서, 문서의 recall 수치가 배포 환경을 설명하지 못한다.

## 3. 응답 속도 (현재 12~20초)

- [ ] **`rag_query` LLM 단계 제거 검토.** 측정 결과 LLM 검색어가 원문·규칙보다 오히려 나빴다
      (사례 8건: 원문 8/8, 규칙 8/8, LLM 6/8). 이슈당 2초를 쓰고 품질이 떨어진다. 42문항
      전체로 재확인한 뒤 규칙 기반으로 고정하거나 단계 자체를 뺀다.

## 4. 시연 품질

- [ ] **`notice_history`가 0건이다.** 대표 민원이 "금리 인상 안내를 못 받았다"인데 안내 이력
      테이블이 비어 있어 "안내 기록 없음"을 근거로 제시할 수 없다. `transactions`도 3건뿐.
      고객 수를 늘리기 전에 CUST-001의 이력부터 두껍게 채운다.
- [ ] 대조군 고객 1명 추가(CUST-002 = 안내를 제대로 받은 고객). 같은 질문에 다른 답이 나오는
      시연이 "내 금융정보와 대조한다"는 차별점을 가장 직접적으로 보여준다.

## 5. 정리

- [ ] 데모 HTML 중복 통합: `demo/agent2~4`는 정적판과 라이브판이 `agent-api.js` 로드 2줄만
      다르고 agent1은 레이아웃이 252줄 갈라졌다. `agent-api.js` 유무로 동작을 나눠 파일 하나로
      합친다. (agent-client 브랜치가 같은 파일을 수정 중이라 머지 이후)
- [x] 중복 엔드포인트 제거: `/mock/accounts/*` 4개와 `/mock/customers/{id}/products`.
      같은 데이터를 Finance MCP의 `get_my_*` tool이 제공하고 파이프라인은 그쪽을 쓴다.
      `review`/`audit`은 처음에 같이 지우려 했으나, hold 민원을 사람이 푸는 유일한 경로라
      남기고 상담원 화면을 만들었다.
- [x] `server/scripts/` 스크립트 용도를 `server/README.md`에 정리했다.
- [ ] **hold가 풀려도 소비자가 모른다.** 상담원이 검토를 마치면 서버 상태는 바뀌고 마이 페이지도
      서버 값을 기준으로 그리지만, 클라이언트에 주기 갱신이 전혀 없고(`setInterval`/`EventSource`
      /`WebSocket` 없음) 마이 페이지 조회는 진입 시 1회뿐이다. 결국 사용자가 우연히 다시 들어오거나
      새로고침해야 결과를 본다. "검토 중"이라고 세워놓고 끝났다고 알려주지 않는 셈.
      → 알림 인프라까지 가지 않아도, 마이 페이지 재조회 버튼이나 화면 복귀 시 refetch,
      "결과 나온 민원 n건" 배지 정도로 대부분 해소된다.

---

## 결정 사항 (다시 논의하지 않기)

- **라우팅(`issue_splitter`)은 LLM 유지.** 실데이터 기준 LLM 91.4% vs 규칙 65.5%로 격차가 크고,
  첫 단계라 여기서 틀리면 이후가 전부 오염된다(`server/tests/evaluate_aihub.py`).
- **관리자 페이지 유지.** 민원 유입량과 에이전트별 fallback 발생률 모니터링이 목적. 자기
  시스템이 언제 LLM 대신 규칙으로 떨어지는지 감시한다는 점에서 유지 가치가 있다.
- **Finance MCP 레이어 유지.** in-process 기본 transport라 코드 층이 한 겹 늘지만, `stdio`
  모드로 실제 MCP 프로토콜을 쓸 수 있게 설계돼 있다.
- **과거 시점 규정 기준 판단은 범위 밖.** 만료 법령을 corpus에서 제외했다. 필요해지면
  `build_corpus --keep-expired`로 되돌린다.

## 협업 규칙

- main에서 작업한다. 브랜치를 나눌 경우 **작업 시작 전에 상대 브랜치를 먼저 pull한다** —
  같은 문제(형태소 분석)를 각자 따로 구현하는 일이 두 번 발생했다.
- `data/` 하위에 대용량 파일을 추가할 때는 gitignore 대상인지 먼저 확인한다. GitHub 100MB
  한도를 넘겨 푸시가 거부된 적이 있다(`server/rag/chunks.jsonl`).
- 실제 고객정보·실제 계좌번호·주민번호는 수집하지 않는다.
