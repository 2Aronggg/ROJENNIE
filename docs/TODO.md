# TODO

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
