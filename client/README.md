# Client

KB Key Buddy의 React Flow 기반 금융 민원 화면입니다.

## 실행

```powershell
cd client
npm install
npm run dev
```

브라우저에서 `http://localhost:5173`으로 접속합니다. 서버 없이 화면만 확인하려면 `http://localhost:5173/?demo=1`을 사용합니다.

서버를 함께 실행하려면 프로젝트 루트에서 가상환경을 먼저 활성화합니다.

```powershell
cd C:\Users\WIN11\ROJENNIE
\.venv\Scripts\Activate.ps1
python -m pip install -r server\requirements.txt
python -m uvicorn server.app:app --reload
```

별도 터미널에서 클라이언트를 실행합니다.

```powershell
cd client
npm run dev
```

기본 API 주소는 `http://localhost:8000`입니다. 필요하면 `VITE_API_BASE`로 변경합니다.

## 화면 흐름

```text
내 금융정보 연결 상태
        ↓
오른쪽 상담 채팅
        ↓
왼쪽 React Flow 민원 트리
        ↓
선택한 민원의 리포트·근거 Drawer
```

- 시작 화면에는 민원 노드를 미리 만들지 않습니다.
- 사용자가 채팅으로 문의를 보내면 Issue Splitter 결과로 민원 노드가 생성됩니다.
- 사용자 답변, 계산 결과, 확인된 사실은 민원별 트리 아래에 추가합니다.
- RAG 후보자료는 별도 노드로 만들지 않고 리포트의 판단 근거에 표시합니다.
- 근거자료를 클릭하면 문서명·페이지·조항·인용문을 Drawer에서 확인합니다.
- 추가 정보가 필요한 민원 단계만 빨간 테두리와 채팅 질문으로 표시합니다.
- 노드에는 내부 고객 ID, 검색 점수, 검색 방식, 원문 전체를 표시하지 않습니다.

## 내 금융정보

실제 은행 내부 시스템 대신 서버의 가상 고객 프로필을 사용합니다.

```text
로그인 세션
→ CUST-001
→ 내 금융정보 MCP Tool
→ 예금·적금·거래내역 조회
```

고객 ID를 사용자가 직접 입력하거나 LLM이 추측하지 않습니다. 조회 동의가 없으면 먼저 동의 안내를 표시합니다.

## API

- `POST /api/v1/cases/analyze`: 문의 분석
- `GET /api/v1/cases/{case_id}`: 민원 트리와 리포트 조회
- `POST /api/v1/cases/{case_id}/review`: Human Review 결과 반영

MCP 호출은 브라우저가 직접 하지 않습니다. FastAPI가 MCP Client가 되어 내 금융정보·RAG·계산 Tool을 호출하고, 결과만 클라이언트에 반환합니다.

## 상태 표시

내부 값과 화면 표시를 분리합니다.

| 내부 값 | 화면 표시 |
|---|---|
| `proceed` | 리포트 생성됨 |
| `ask` | 추가 정보 필요 |
| `amend` | 보완 필요 |
| `hold` | 검토 대기 |

## 구조

```text
client/
├─ index.html
├─ package.json
└─ src/
   ├─ main.jsx
   └─ style.css
```

## 제외

- 금융회사·금융감독기관에 민원 자동 제출
- 계좌·계약 정보 변경
- 대출 민원 처리
- 브라우저에서 MCP 서버 직접 호출
