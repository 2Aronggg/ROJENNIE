# A TODO: 데이터·서버

브랜치: `feat/data-server`

## P0

- [x] PDF 텍스트 추출 및 페이지·조항 단위 chunk 생성
- [x] `doc_id`, `doc_type`, `product`, `issue_types`, `source`, `effective_from` 메타데이터 부여
- [x] 문서 시행일과 사건일을 비교하는 Fact Resolver 구현
- [x] 공통 case schema와 API Pydantic 모델 정의
- [x] 공통 규정·상품 문서 최소 검색 파이프라인 구현
- [x] 검색 결과에 문서명·페이지·조항 연결
- [x] `single_issue_75.json`, `complex_issue_75.json` 로더 작성
- [x] `ground_truth_subissues` 기반 분해 평가기 작성
- [x] `POST /api/v1/cases/analyze` 구현
- [x] `GET /api/v1/cases/{case_id}` 구현

## P1

- [ ] Vector Search와 Full-Text Search 결합
- [ ] 사건 그래프에 날짜·금액·문서·답변 관계 저장
- [ ] `POST /api/v1/cases/{case_id}/review` 구현
- [ ] 문서 변경 감지와 재색인
- [ ] 규정 시행일 변경 알림
- [ ] 근거·모델 출력·사용자 수정 이력 audit log

## A가 B에게 제공할 계약

- [x] case schema
- [x] API request/response 예시
- [x] `evidence_refs` 형식
- [x] 결정 상태 enum
- [x] 오류·누락 정보 응답 형식

## 데이터 추가는 후순위

- [ ] 공식 분쟁조정·민원 사례 원문 수집
- [ ] 공식 민원 절차·제출서류 정보 수집
- [ ] 보험 범위를 유지할 경우 보험 문서 수집