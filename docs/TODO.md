# TODO

앞으로 할 일만 적는다. 완료된 항목은 다음 작업의 전제가 될 때만 `[x]`로 남기고, 나머지 이력은 git log에 있다.

## 1. 화면에 안 나오는 서버 결과 연결

서버가 계산해서 내려보내는데 클라이언트가 버리는 값들이다. 데이터가 이미 있어서 렌더링만 붙이면 된다.

- [x] **논리 검증 결과(`support_chains`, `unsupported_claims`)를 리포트에 표시한다.**
      "검색 결과를 곧바로 결론으로 쓰지 않는다"가 이 서비스의 핵심인데, 그걸 증명하는 화면이
      없었다. 이제 claim별 연결 근거와 유형(`direct_match`/`analogical`/`unverified`),
      뒷받침되지 않은 주장을 리포트와 생성된 민원 화면에 보여준다.
- [x] 컴플라이언스 차단 표시(`compliance_blocked`, `compliance_flags`). LLM이 단정 표현을 써서
      차단되면 사용자는 답변이 왜 조정됐는지 모른다. 차단 메시지와 조정 사유를 표시한다.
- [x] 시점 필터가 작동했다는 표시. 사건 당시 시행 중이던 규정만 썼다는 건 강한 근거인데
      이제 이슈별 검색 기준일과 후보자료의 시행일 표시 여부를 함께 보여준다.

## 2. 배포 (Vercel + Supabase)

- [x] **브랜치 통합 완료.** `feat/data-server`와 `feat/agent-client`를 main으로 합쳤다.
      형태소 분석은 data-server 구조(전체 청크 빌드타임 토큰화) + agent-client 품사 세트를
      채택했고, 원격 main에 미해결 충돌 마커가 커밋돼 있던 것도 복구했다. 이후 작업은 main에서 한다.
- [x] corpus를 배포 번들에 포함 — `.gitignore`가 `data/corpus/all.jsonl`만 예외로 추적한다
      (37.5MB, 서버가 읽는 유일한 corpus 파일). 나머지 per-corpus 파일은 중복이라 계속 제외.
- [x] Mock Bank의 읽기 전용 파일시스템 대응 — `MOCK_BANK_DB=:memory:`로 인메모리 SQLite를
      쓰고, 파일 쓰기가 실패하면 자동으로 인메모리로 넘어간다. 시드 데이터를 매번 상수에서
      다시 쓰기 때문에 파일이 없어도 동작이 같다.
- [x] `vercel.json` + `api/index.py` 진입점 추가. 번들 크기는 문제가 아니었다 — Fluid Compute는
      5GB까지 지원하고 현재 의존성은 약 214MB(kiwipiepy 모델 105MB 포함)다.
- [x] Vercel 환경변수 설정과 실제 배포 실행. `keybuddy-ten.vercel.app`에 올라갔고 함수는 기동한다.

- [x] **모든 경로가 404였던 것 수정.** 프로젝트 framework 프리셋이 `python`이라
      (`.vercel/output/builds.json`) FastAPI 함수가 도메인 전체를 잡는데, `vercel.json`
      rewrite는 함수가 `/api/*` 아래 있다고 가정하고 경로 앞에 `/api`를 붙이고 있었다.
      `/health` → `/api/health`, `/api/v1/x` → `/api/api/v1/x`가 되어 매칭이 안 됐다
      (FastAPI가 직접 `{"detail":"Not Found"}`를 돌려준 것이지 Vercel 404 페이지가 아니었다).
      → rewrite를 전부 걷어내고 정적 SPA는 `server/app.py` 끝에서 `StaticFiles(html=True)`로
      mount한다. catch-all과 SPA fallback이 같은 `/(.*)`를 두고 싸우지 않는다.
      **mount는 반드시 모든 API 라우트 등록 뒤에 와야 한다** — Starlette는 등록 순서로 매칭해서
      `/`에 먼저 걸면 API 경로를 전부 가로챈다.
- [x] **`.vercelignore`의 `data` 통째 제외 수정.** 10MB 초과의 진범은
      `server/rag/embeddings.jsonl`(510MB)과 `chunks.jsonl`(104MB)이었다. 이제 원천 문서는
      계속 빼되 서버가 런타임에 읽는 3개(`corpus/all.jsonl`, `corpus/manifest.json`,
      `dictionary/fine_financial_glossary.json`)만 되살린다. gitignore 규칙상 부모 디렉터리가
      제외되면 안쪽 파일을 되살릴 수 없어서 `data/*` → `!data/corpus` → `data/corpus/*` →
      `!data/corpus/all.jsonl` 식으로 단계별로 열어야 한다.
- [x] **pgvector 대신 로컬 하이브리드 인덱스를 쓴다.** `SUPABASE_RAG_ENABLED=false`.
      pgvector RPC(`match_rag_chunks`)는 순수 벡터 유사도만 써서 형태소 텍스트 점수·상품명
      가중치·intent 보정이 전부 빠진다. 문서의 recall@5 = 100%는 로컬 하이브리드 경로에서
      측정한 값이라, pgvector로 배포하면 그 수치가 배포 환경을 설명하지 못한다.
      corpus가 3,698청크까지 줄어 인메모리로 충분하다.
- [ ] 배포 후 `/api/v1/cases/analyze`가 실제 근거를 반환하는지, 콜드 스타트가 몇 초인지 잰다.
      인덱스가 로컬에서 855MB를 쓰는데 함수 메모리는 2048MB다. 여유가 크지 않다.

## 3. 로컬 기동이 갑자기 10분 넘게 걸릴 때

`retrieval.needs_reindex`가 원천 문서의 mtime을 `data/corpus/all.jsonl`의 mtime과 비교해서,
하나라도 더 새것이면 PDF 307개 + 법령 JSON 7만여 개를 **전부 다시 파싱한다.** 문제는 git이
checkout·rebase·stash pop 때 파일 mtime을 그 시각으로 새로 찍는다는 것이다. 실제로 rebase
직후 PDF 한 개가 all.jsonl보다 13밀리초 새것이 되어 전체 재색인이 돌았고, 85초짜리 테스트가
15분 넘게 멈춰 있었다. 내용은 하나도 안 바뀐 상태였다.

- [ ] mtime 비교를 내용 기준으로 바꾼다. `manifest.json`에 원천 파일 목록의 해시나 크기를
      적어 두고 그걸 비교하면 git이 mtime을 건드려도 오탐하지 않는다.
- 당장 막혔으면 `all.jsonl`의 mtime만 현재로 올리면 된다(내용이 최신인 게 확실할 때).
- 배포본은 영향이 없다. `.vercelignore`가 원천 문서를 빼서 비교 대상이 0개라 항상 all.jsonl을
  그대로 읽는다.

## 4. 응답 속도 (현재 12~20초)

- [ ] **`rag_query` LLM 단계 제거 검토.** 측정 결과 LLM 검색어가 원문·규칙보다 오히려 나빴다
      (사례 8건: 원문 8/8, 규칙 8/8, LLM 6/8). 이슈당 2초를 쓰고 품질이 떨어진다. 42문항
      전체로 재확인한 뒤 규칙 기반으로 고정하거나 단계 자체를 뺀다.

## 5. 시연 품질

- [ ] **`notice_history`가 0건이다.** 대표 민원이 "금리 인상 안내를 못 받았다"인데 안내 이력
      테이블이 비어 있어 "안내 기록 없음"을 근거로 제시할 수 없다. `transactions`도 3건뿐.
      고객 수를 늘리기 전에 CUST-001의 이력부터 두껍게 채운다.
- [ ] 대조군 고객 1명 추가(CUST-002 = 안내를 제대로 받은 고객). 같은 질문에 다른 답이 나오는
      시연이 "내 금융정보와 대조한다"는 차별점을 가장 직접적으로 보여준다.

## 6. 데이터 품질

- [x] **중복 PDF 10개 삭제 완료.** 본문 해시로 판별해 5종의 사본만 지웠다(예금거래기본약관은
      6개 파일이 본문까지 동일했다). 상품 문서 135 → 125개, 청크 886 → 796개.
      삭제 후에도 retrieval 42/42 = 100%가 유지된다. 이걸 우회하려고 평가셋에 있던
      `CANONICAL_DOC_IDS`(중복 doc_id를 모두 정답으로 인정)도 함께 제거했다.
      → **다음에 정리할 때도 파일명으로 지우면 안 된다.** `약관 및 상품설명서 (1)~(12)`는
      브라우저 기본 이름일 뿐 속은 거치식예금 약관, KB모임금고 특약처럼 서로 다른 문서다.
      반드시 본문 해시로 판단할 것.
- [x] 표시용 문서 제목을 본문에서 추출(`ingest._document_title`). 파일명을 바꾸면 `doc_id`가
      경로 해시라 평가셋 정답이 전부 깨지므로, 파일은 두고 제목만 뽑아 `DocumentChunk.doc_title`에
      담는다. 상품 청크 796개 전부 제목이 채워졌다.

## 7. 정리

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

- **라우팅(`issue_splitter`)은 LLM 유지.** 2026-08-03 재측정으로 LLM 49.6% vs 규칙 43.2%
  (`server/tests/evaluate_aihub.py`). 예전에 적었던 91.4% vs 65.5%는 재현되지 않아 철회했다.
  격차는 6.4%p로 줄었지만 방향은 그대로고, 첫 단계라 여기서 틀리면 이후가 전부 오염된다.
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
