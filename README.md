# KB Key Buddy

<<<<<<< HEAD
KB Key Buddy(ROJENNIE)는 복합 금융 민원을 이슈 단위로 분리하고, mock 금융 데이터와 RAG 문서 근거를 함께 확인해 안전한 다음 행동을 안내하는 금융소비자 보호 프로토타입입니다.

현재 MVP는 예금, 적금, 대출 관련 민원을 중심으로 동작합니다. 실제 은행 내부 시스템이나 실고객 데이터에는 연결되어 있지 않으며, 금융 데이터는 mock SQLite와 시연용 데이터로 구성되어 있습니다.

## 핵심 기능

- 복합 금융 민원 이슈 분리
- 예금/적금/대출별 확인 항목 구성
- mock 고객 계약/거래/금리/안내 이력 조회
- 약관, 상품설명서, 규정, 사례, 절차 안내 RAG 검색
- 근거-결론 지지 검증
- `proceed / ask / amend / hold` 상태 결정
- 안전한 사용자 리포트와 다음 행동 안내

## 기술 구조

```text
사용자 민원 입력
  -> Case Builder
  -> Mock Customer Data Resolver / Finance MCP
  -> RAG Retrieval
  -> Logic Verification
  -> Decision Gate
  -> Report Composer
  -> CaseAnalysis 응답
```

발표에서 말하는 Agent 1~4는 논리적 파이프라인 단계입니다. 현재 구현은 독립 에이전트 서버가 아니라 Python 모듈과 deterministic rule 기반 파이프라인으로 구성되어 있으며, 일부 단계만 정책 게이트 뒤에서 LLM을 선택적으로 사용합니다.

## 현재 평가 수치

- RAG 평가셋: 42문항
- 전체 Recall@5: 100.0% (42/42)
- cases Recall@5: 100.0% (16/16)
- products Recall@5: 100.0% (20/20)
- guides Recall@5: 100.0% (6/6)
- corpus 규모: 65,764 chunks
- 테스트 수: 75개

## 안전 원칙

- 검색 결과를 곧바로 결론으로 사용하지 않습니다.
- 약관/규정/상품설명서는 직접 근거로 사용합니다.
- 분쟁조정 사례와 판례는 유사 사례 참고로만 사용합니다.
- 민원 절차 문서는 다음 행동 안내에만 사용합니다.
- 근거가 부족하면 `ask` 또는 `hold`로 안전하게 멈춥니다.
- 배상 가능성, 은행 과실, 위법 여부를 자동 확정하지 않습니다.

## 주요 문서

| 문서 | 내용 |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항과 MVP 범위 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 기술 아키텍처와 파이프라인 |
| [docs/TECHNICAL_EVALUATION.md](docs/TECHNICAL_EVALUATION.md) | 검색/평가/안전성 수치 |
| [docs/LOGIC_AUDIT.md](docs/LOGIC_AUDIT.md) | 근거-결론 감사 레이어 |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | 실제/공개/합성 데이터 경계 |
| [docs/AGENT_MODULE_MAPPING.md](docs/AGENT_MODULE_MAPPING.md) | 발표용 Agent와 실제 모듈 매핑 |
| [docs/PRIVACY_HANDLING.md](docs/PRIVACY_HANDLING.md) | 개인정보 처리 현황과 한계 |
| [server/README.md](server/README.md) | 서버 실행과 백엔드 모듈 구조 |

## 로컬 실행

```powershell
cd C:\Users\achim\ROJENNIE
python -m pip install -r server\requirements.txt
python -m uvicorn server.app:app --reload
```

retrieval 평가:

```powershell
python -m server.tests.evaluate_retrieval
```

core 테스트 예:

```powershell
python -m pytest server/tests/test_facts.py server/tests/test_logic_audit.py
```
=======
**예금·적금·대출 민원을 입력하면, 내 계좌 기록과 현행 규정을 대조해 근거와 함께 답합니다.**

금융 소비자가 겪은 문제를 민원 단위로 나누고, 사용자의 실제 계약·거래 이력과 규정·약관·분쟁조정 사례를 함께 확인해서 "무엇이 확인됐고 무엇이 부족한지"를 근거와 함께 알려주는 서비스입니다.

## 하는 것 / 하지 않는 것

| 한다 | 하지 않는다 |
|---|---|
| 복합 민원을 상품별 이슈로 분리 | 법적 책임·배상 여부 확정 |
| 내 계약·거래·금리·안내 이력과 대조 | 민원 자동 접수·외부 제출 |
| 현행 규정·약관·사례에서 근거 검색 | 계좌·계약 변경 |
| 근거를 인용한 리포트 생성 | 사건 당시(과거) 규정 기준 판단 |
| 정보가 부족하면 되묻고, 위험하면 사람에게 넘김 | 법률 자문 |

지원 상품은 **예금·적금·대출**입니다. 보험·카드·상조 등은 범위 밖임을 명시적으로 안내합니다.

근거 검색은 **오늘 시행 중인 규정**을 기준으로 합니다. 과거 시점 기준 판단은 지원하지 않습니다(필요해지면 `build_corpus --keep-expired`로 과거 개정판까지 포함한 corpus를 다시 만들 수 있습니다).

## 처리 흐름

```text
민원 입력
  → 이슈 분리          Case Builder (LLM, 실패 시 규칙 기반)
  → 내 금융정보 조회    Finance MCP → Mock Bank
  → 근거 검색          형태소 기반 텍스트 + 벡터 하이브리드 RAG
  → 논리 검증          근거가 결론을 실제로 뒷받침하는지 확인
  → 판단               Decision Gate (LLM 아님, 결정적 규칙)
  → 리포트             민원내용·처리결과·유의사항·후속절차
```

판단 상태는 `proceed`(안내 가능) / `ask`(추가 확인 필요) / `amend`(개인정보 정리 필요) / `hold`(사람 검토)이며, **LLM은 문장만 쓰고 이 상태를 뒤집지 못합니다.**

## 안전 장치

- **Decision Gate가 결정적 로직**: 법적 책임·배상 같은 판단은 규칙이 정하고 LLM은 관여하지 않습니다.
- **LLM Policy Gateway**: 모든 LLM 호출 전후로 주민번호·계좌번호·카드번호·연락처를 마스킹하고 감사 로그를 남깁니다.
- **컴플라이언스 후처리**: "배상 얼마 받을 수 있다" 같은 단정을 프롬프트 지시가 아니라 출력 필터로 실제 차단하고, 걸리면 안전한 문구로 대체합니다.
- **LLM 실패 시 규칙 기반 fallback**: Gemini 장애에도 서비스가 멈추지 않습니다. 관리자 페이지에서 fallback 발생률을 모니터링합니다.
- 사용자가 이미 말한 값은 다시 묻지 않고, 화면에 검색 점수·내부 chunk ID를 노출하지 않습니다.

## 데이터

| 종류 | 출처 | 규모 |
|---|---|---|
| 법령·가이드라인 | 국가법령정보센터, 금융위 | 현행 12개 문서 |
| 상품설명서·약관 | KB국민은행 | 135개 문서 |
| 분쟁조정 사례·판례 | 금융감독원, 한국소비자원, 법제처 | 29건 |
| 가상 고객·계약·거래 | 자체 생성 (SQLite) | 고객 1명 |

실제 고객정보·계좌번호·주민번호는 사용하지 않습니다. Mock Bank는 가상 고객 `CUST-001` 한 명의 합성 데이터만 가집니다.

검색 성능은 자체 평가셋 42문항 기준 **recall@5 97.6%** 입니다(`server/tests/evaluate_retrieval.py`). 상품 라우팅은 AIHub 실제 상담 데이터로 검증했습니다(`server/tests/evaluate_aihub.py`).

## 실행

```bash
# 서버
python -m pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload

# 클라이언트 (별도 터미널)
cd client && npm install && npm run dev
```

`.env`에 `GEMINI_API_KEY`가 없으면 전 단계가 규칙 기반으로 동작합니다. 자세한 실행 방법은 [server/README.md](server/README.md), [client/README.md](client/README.md)를 참고하세요.

corpus를 다시 만들려면 (원천 문서를 추가·수정했을 때):

```bash
python -m server.rag.ingest --data-dir data --output server/rag/chunks.jsonl
python -m server.rag.embed_corpus   # Gemini API 비용 발생
python -m server.rag.build_corpus
```

## 디렉터리

```text
client/              React 제품 화면 (index.html)
client/demo/         에이전트별 데모 페이지
server/app.py        FastAPI 오케스트레이터
server/agents/       이슈 분리·검색어·논리검증·결정·리포트
server/policy/       LLM 호출 정책 게이트
server/rag/          청킹·임베딩·검색
server/mcp/finance/  읽기 전용 금융 Tool
server/tests/        회귀 테스트 + 성능 평가 스크립트
data/                RAG 원천 문서, corpus, 평가 데이터
docs/                아키텍처·기술 평가·TODO
```

## 문서

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 현재 코드 기준 구조
- [docs/TECHNICAL_EVALUATION.md](docs/TECHNICAL_EVALUATION.md) — 데이터·설계·개선 과정의 근거와 측정치
- [docs/TODO.md](docs/TODO.md) — 앞으로 할 일
>>>>>>> e11d3ba8296a3fd7ba7d6143abed7de0bbda7be6

## 범위와 한계

<<<<<<< HEAD
현재 프로젝트는 제출/시연용 프로토타입입니다.

- 실제 은행 API 연동 없음
- 실제 고객 개인정보 저장 없음
- mock 고객 `CUST-001` 중심
- 운영용 vector DB 미도입
- UI 데모 HTML과 실제 API 앱은 역할이 다름
- 개인정보 마스킹과 운영 감사 로그는 production 수준 추가 구현 필요

## 발표용 한 줄

> KB Key Buddy는 RAG로 근거를 찾는 데서 멈추지 않고, 그 근거가 결론을 실제로 지지하는지 검증해 금융 민원에서 위험한 자동 판단을 막는 안전 중심 분석 파이프라인입니다.
=======
이 서비스는 금융회사나 금융감독기관의 최종 판단, 법률 자문, 민원 자동 접수를 대신하지 않습니다. 최종 판단은 정식 금융 민원 절차(금융감독원 분쟁조정 등)를 통해 확인해야 합니다.
>>>>>>> e11d3ba8296a3fd7ba7d6143abed7de0bbda7be6
