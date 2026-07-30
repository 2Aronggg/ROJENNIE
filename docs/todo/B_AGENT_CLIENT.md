# B TODO: 에이전트·클라이언트

담당 브랜치: `feat/agent-client`

담당 범위는 세 개의 에이전트, Decision Gate 연동, React Flow와 상담 UI다. `data/`, `server/mock_data.py`, `server/retrieval.py`, `server/finance_mcp/`는 수정하지 않고 A의 계약을 사용한다.

## P0: 에이전트 구조

- [x] Case Builder 내부 Issue Splitter 구현
- [x] Case Builder 내부 Focal Builder 구현
- [x] 사용자 문의에서 필수 사실 추출
- [x] 사용자가 이미 입력한 금액·금리·거래 사실 재질문 방지
- [ ] `customer_ref`와 `my_info_refs`를 Case에 연결
- [ ] MCP Tool 결과를 Evidence & Decision Agent 입력으로 연결
- [ ] Evidence & Decision Agent가 사용자 진술·내 금융정보·RAG 후보를 구분
- [ ] RAG 후보를 Logic Verification 전에 확정 근거로 사용하지 않도록 처리
- [x] Logic Verification의 `supported / unsupported / unknown / conflict` 출력
- [x] `proceed / amend / ask / hold` Decision Gate
- [x] 개인정보 Content Scope 규칙
- [x] 복합 민원을 섞지 않는 Response Composer
- [x] 명의도용·개인정보 민원의 `hold` 안전 테스트

## P1: 리포트·대화

- [x] `민원내용 / 처리결과 / 소비자 유의사항` 리포트 형식
- [x] 제출 서류·후속 절차 표시
- [ ] RAG 후보자료를 리포트 판단 근거에 묶기
- [ ] 근거 클릭 시 문서명·페이지·조항·인용문 Drawer 표시
- [ ] 검색 점수·검색 방식·내부 chunk ID 숨김
- [x] `ask` 상태에서 필요한 질문 표시
- [x] 사용자의 추가 답변으로 재분석
- [ ] 내 금융정보 조회 동의 UI
- [ ] 조회된 상품·거래내역을 상담 맥락에 표시
- [ ] MCP Tool 호출 상태를 상담 기록에 표시

## P1: 클라이언트

- [x] 문의 입력·파일 첨부 화면
- [x] 시작 시 빈 React Flow 화면
- [x] 분석 후 민원별 노드 생성
- [x] 민원별 결과 카드와 처리 상태
- [x] React Flow 드래그·확대·축소·화면 이동
- [x] 사용자 답변·계산 결과 노드 생성
- [x] 노드 선택 및 연결 경로 강조
- [ ] 근거자료 상세 Drawer
- [ ] 리포트 생성 시 중앙 확대 화면
- [x] `ask` 단계만 빨간 테두리 표시
- [x] 내부 결정 상태의 한글 표시
- [ ] `hold` Human Review 대기 화면

## A와 통합할 때 확인

- [ ] A의 API schema를 기준으로 client 타입 작성
- [ ] `customer_ref`, `consent_status`, `my_info_refs` 표시 범위 확인
- [ ] MCP 결과를 브라우저가 직접 호출하지 않음
- [ ] `issue_id`별 내 금융정보·검색·검증·답변 결과 연결
- [ ] `evidence_refs` 클릭 시 문서 페이지·섹션 표시
- [ ] `proceed / amend / ask / hold` 상태 표시가 API와 일치함
- [ ] 사용자 입력 사실이 이미 있으면 추가 질문하지 않음
- [ ] 외부 제출 없이 분석 결과만 표시함
- [ ] 대출 관련 분기·문구가 없음

## 검증 명령

```powershell
cd client
npm run build
```

서버 연동 검증은 A의 API와 MCP가 실행된 상태에서 진행한다.
