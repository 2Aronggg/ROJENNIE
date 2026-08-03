# KB Key Buddy

**복합 금융 민원을 사건 단위로 나누고, 내 금융정보와 규정 근거를 연결해 다음 행동을 안내하는 금융 민원 지원 에이전트입니다.**

KB Key Buddy는 사용자가 입력한 예금·적금·대출 관련 민원을 분석해 여러 쟁점으로 분리하고, 각 쟁점마다 필요한 사실관계와 근거 문서를 연결해 안내합니다.  
예를 들어 하나의 민원 안에 “우대금리 미적용”, “수수료 안내 불일치”, “금리 인상 미통지”가 함께 들어 있어도 이를 각각의 사건으로 나누고, 사건별로 확인된 정보와 추가로 필요한 자료를 정리합니다.

이 서비스는 단순 챗봇이 아니라, **사용자의 금융 거래 이력**, **상품 약관**, **현행 규정**, **분쟁조정 사례**, **민원 접수 안내**를 함께 활용해 소비자가 민원을 준비할 때 필요한 근거와 절차를 구조화해주는 것을 목표로 합니다.

---

## 서비스 개요

금융 민원은 한 문장처럼 보이더라도 실제로는 여러 사건이 섞여 있는 경우가 많습니다.

예를 들어 사용자가 다음과 같이 입력할 수 있습니다.

> “적금 우대금리가 적용되지 않았고, 중도해지 수수료도 안내받은 것과 다르게 나온 것 같습니다.”

이 경우 KB Key Buddy는 이를 하나의 답변으로 뭉개지 않고 다음처럼 분리합니다.

1. 적금 우대금리 미적용 이슈
2. 중도해지 수수료 안내 불일치 이슈

각 이슈에 대해 다음 정보를 따로 확인합니다.

- 어떤 상품과 관련된 민원인지
- 사용자가 이미 말한 사실은 무엇인지
- 내 계약·거래·금리·안내 이력에서 확인되는 정보는 무엇인지
- 약관이나 상품설명서에서 직접 근거가 있는지
- 사례나 판례는 참고 가능한 유사 사례인지
- 추가로 필요한 서류나 확인 질문은 무엇인지
- 지금 단계에서 안내 가능한지, 사람 검토가 필요한지

---

## 핵심 기능

### 1. 복합 민원 이슈 분리

사용자가 하나의 문장에 여러 금융 문제를 함께 입력해도, Case Builder가 민원을 상품별·쟁점별로 분리합니다.

예시:

```text
예금 만기 이자가 예상보다 적고, 대출 금리 인상 안내도 못 받았습니다.





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
| 법령·가이드라인 | 국가법령정보센터, 금융위원회	금융소비자 보호 및 금융거래 관련 규정 | 
| 상품설명서·약관 | KB국민은행 | 
| 분쟁조정 사례·판례 | 금융감독원, 한국소비자원,  법제처	유사 민원 판단 사례 | 
| 가상 고객·계약·거래 | 자체 생성 (SQLite) | 

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

## 배포 

`vercel.json`과 `api/index.py`가 준비돼 있습니다. 클라이언트는 정적 빌드로, FastAPI는 서버리스 함수로 나갑니다.

환경변수를 먼저 설정하세요:

| 변수 | 값 | 이유 |
|---|---|---|
| `GEMINI_API_KEY` | 발급받은 키 | 없으면 전 단계가 규칙 기반으로 동작 |
| `MOCK_BANK_DB` | `:memory:` | 서버리스는 파일시스템이 읽기 전용 |
| `CORS_ORIGINS` | 배포 도메인 | 기본값은 localhost만 허용 |

`data/corpus/all.jsonl`(36.8MB)은 저장소에 포함돼 있어야 합니다. 서버가 읽는 유일한 corpus 파일이고, 없으면 근거 검색이 빈 인덱스로 시작합니다.

## 실행 방법

서버 실행:
```bash
python -m pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload
```

클라이언트 실행:
```bash
cd client
npm install
npm run dev
```

테스트 실행:
```bash
python -m pytest server/tests
```

Windows PowerShell에서 가상환경을 사용할 경우:
```bash
.\.venv\Scripts\Activate.ps1
python -m pytest server/tests
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

## 팀 역할 분담

yvz1225 — Data Server / RAG / 배포

RAG corpus 구축
약관·상품설명서·규정·사례 데이터 정리
형태소 기반 검색 구조 구현
pgvector 및 Supabase 연동 검토
Vercel 배포 구성
서버리스 환경 대응
검색 성능 평가 및 개선


2Aronggg — Agent Client / 서비스 안전성 / 데모

복합 민원 이슈 분리 흐름 구현
Decision Gate 안전 로직 보강
case-level high-risk 전파 구현
개인정보 마스킹 및 출력 안전성 검토
에이전트별 데모 화면 구성
발표 시나리오 정리
사용자 응답 리포트 구조 개선


## 주의

이 서비스는 금융회사나 금융감독기관의 최종 판단, 법률 자문, 민원 자동 접수를 대신하지 않습니다. 최종 판단은 정식 금융 민원 절차(금융감독원 분쟁조정 등)를 통해 확인해야 합니다.
