# B TODO: 에이전트·클라이언트
ㅎㅎㅎ
브랜치: `feat/agent-client`

## P0

- [ ] Issue Splitter 프롬프트와 JSON 출력 검증
- [ ] Focal Builder의 focal·target·missing facts·evidence refs 추출 구현
- [ ] Logic Verification의 `supported / unsupported / unknown / conflict` 출력 구현
- [ ] `proceed / amend / ask / hold` Decision Gate 구현
- [ ] 개인정보 Content Scope 규칙 적용
- [ ] 복합 민원을 섞지 않는 Response Composer 템플릿 구현
- [ ] 명의도용·개인정보 민원의 `hold` 안전 테스트 작성
- [ ] 문의 입력·파일 첨부 화면 구현
- [ ] 민원별 결과 카드와 처리 상태 구현
- [ ] 근거 문서 상세 패널 구현
- [ ] 누락 정보·제출 서류 체크리스트 구현
- [ ] `hold` Human Review 대기 화면 구현

## P1

- [ ] 사용자 추가 답변으로 `ask` 상태 재분석
- [ ] 복합 민원 통합 답변의 cross-issue contradiction 검사
- [ ] 계좌번호·주민번호·전화번호 PII 마스킹 테스트
- [ ] React Flow 처리 상태 시각화
- [ ] 용어를 쉬운 설명으로 바꾸는 답변 품질 테스트

## A와 통합할 때 확인

- [ ] A의 API schema를 기준으로 client 타입 작성
- [ ] `issue_id`별 검색·검증·답변 결과 연결
- [ ] `evidence_refs` 클릭 시 문서 페이지·섹션 표시
- [ ] `proceed / amend / ask / hold` 상태 표시가 API와 일치함
- [ ] 외부 제출 없이 분석 결과만 표시함
