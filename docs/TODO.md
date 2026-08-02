# TODO

<<<<<<< HEAD
현재 문서는 제출/발표 전 남은 작업을 우선순위별로 정리합니다.

## 1. 완료된 핵심 작업

- 복합 민원 이슈 분리 파이프라인 구성
- mock bank / Finance MCP 조회 구조 구성
- RAG corpus 구축
- guides corpus 추가
- PDF `extraction_mode="layout"` 적용
- `Fact.source_type` 기반 provenance 정리
- mock bank fact를 `SYSTEM_INFERRED`로 태깅
- Evidence-Conclusion Audit Layer 도입
- Decision Gate에 unsupported/unverified claim 제동 추가
- Report Composer 금지 표현 필터 추가
- retrieval 평가 42문항 기준 100.0% 확인
- 주요 문서 인코딩 정상화

## 2. 제출 전 우선순위

### P0. 발표 자료 반영

- [ ] 기술 아키텍처 PPT에 최신 수치 반영
- [ ] Agent 1~4가 “논리적 pipeline role”임을 명확히 표기
- [ ] 실제 데이터와 데모 데이터 경계 표기
- [ ] `proceed`가 결론 확정이 아니라 다음 단계 안내 가능 상태임을 표기
- [ ] 분쟁조정 사례는 직접 근거가 아니라 참고 근거임을 표기

### P1. 백엔드 검증

- [ ] `pytest` core 범위 재확인
- [ ] `test_facts.py` 통과 확인
- [ ] `test_logic_audit.py` 통과 확인
- [ ] retrieval 평가 결과를 발표 자료에 반영
- [ ] 전체 pytest 실패 원인이 외부 의존성인지 구분

### P2. 데이터/RAG

- [ ] 놓친 retrieval 케이스 1개 분석
- [ ] canonical_doc_id mapping 확대
- [ ] 사례/판례 데이터 추가 확충
- [ ] 기관별 절차 안내 데이터 추가
- [ ] Support Accuracy 지표 정의

### P3. Client/API 연동

- [ ] 실제 client가 `POST /api/v1/cases/analyze` 응답을 카드로 렌더링하도록 연결
- [ ] `GET /api/v1/cases/{case_id}` 결과 조회 연결
- [ ] missing_facts 질문 UI 정리
- [ ] evidence_refs 상세 보기 UI 정리

## 3. 안전성 체크리스트

- [x] 검색 결과와 최종 결론을 분리
- [x] 직접 근거와 유사 사례를 구분
- [x] 근거 없음 + proceed 차단
- [x] 유사 사례-only + proceed 차단
- [x] mock 금융 데이터 source_type 정리
- [x] report 금지 표현 필터
- [ ] 개인정보 마스킹 테스트 확대
- [ ] 운영용 audit log 저장소 정리
- [ ] human review queue 구체화

## 4. 데이터 경계

실제/공개 reference:

- 약관
- 상품설명서
- 규정/법령
- 분쟁조정/판례 사례
- 민원 접수/처리 절차 안내

시연/합성:

- mock 고객 `CUST-001`
- demo HTML의 화면 텍스트
- 평가셋의 테스트 민원

금지:

- demo 데이터를 실제 고객 사례처럼 설명
- mock bank를 실제 은행 API처럼 설명
- 분쟁조정 사례를 사용자 사안의 직접 결론처럼 설명

## 5. 커밋 전 확인

커밋할 때 제외할 파일:

- Python installer `.exe`
- Python install log
- `.pytest_cache`
- 개인 로컬 설정
- unrelated UI 변경

권장 커밋 단위:

- data/RAG 수정
- logic audit 수정
- 문서 정상화
- UI/HTML 수정

## 6. 발표용 마지막 문장

> 우리는 검색 정확도를 높이는 데서 멈추지 않고, 검색된 근거가 결론을 실제로 지지하는지 검증하는 감사 레이어를 추가했습니다. 그래서 시스템은 근거가 부족한 사안에서 무리하게 답하지 않고, 추가 질문이나 사람 검토로 안전하게 전환합니다.
=======
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

아래 3개는 "나중에"가 아니라 **배포하는 순간 막히는** 것들이다.

- [ ] **corpus가 배포 번들에 없다.** `.gitignore:11`이 `data/corpus/*.jsonl`을 제외하는데
      런타임은 `data/corpus/all.jsonl`을 읽는다(`server/app.py:67`). 배포하면 근거 문서가 0건이다.
      만료 법령 제거로 `all.jsonl`이 35MB까지 줄어 커밋이 가능해졌으니, `all.jsonl`만 추적
      대상으로 되돌린다(나머지 per-corpus 파일은 중복이라 계속 제외).
- [ ] **Mock Bank가 시작할 때마다 파일에 쓴다.** `MockBankClient._initialize()`가
      `mkdir` + `INSERT OR REPLACE`를 실행하는데(`server/finance/mock_data.py:180`), 서버리스는
      파일시스템이 읽기 전용이라 기동에 실패한다. sqlite 파일도 gitignore돼 있어 번들에 없다.
      → 메모리 SQLite(`:memory:`)로 매 요청 시드하거나, 고객 데이터를 Supabase로 옮긴다.
- [ ] **`vercel.json`과 진입점이 없다.** FastAPI를 Vercel에 올리려면 `api/` 진입점 구성이 필요하다.
      `kiwipiepy` 모델이 105MB라 서버리스 번들 한도(압축 250MB)에 여유가 크지 않으니, 배포 전에
      번들 크기를 한 번 확인한다.
- [ ] 위 3개 해결 후 pgvector 사용 여부 결정. corpus가 3,787청크/인덱스 8.4초까지 줄어서
      인메모리로도 배포 가능할 수 있고, 그러면 pgvector 경로를 유지할 이유가 없다.
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
- [ ] 사용되지 않는 엔드포인트 제거: `/api/v1/cases/{id}/review`, `/api/v1/cases/{id}/audit`,
      `/mock/accounts/*` 4개, `/mock/customers/{id}/products`. 클라이언트도 MCP도 호출하지 않는다.

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
>>>>>>> e11d3ba8296a3fd7ba7d6143abed7de0bbda7be6
