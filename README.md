# KB Key Buddy

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
- 전체 Recall@5: 97.6% (41/42)
- cases Recall@5: 93.8% (15/16)
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

## 범위와 한계

현재 프로젝트는 제출/시연용 프로토타입입니다.

- 실제 은행 API 연동 없음
- 실제 고객 개인정보 저장 없음
- mock 고객 `CUST-001` 중심
- 운영용 vector DB 미도입
- UI 데모 HTML과 실제 API 앱은 역할이 다름
- 개인정보 마스킹과 운영 감사 로그는 production 수준 추가 구현 필요

## 발표용 한 줄

> KB Key Buddy는 RAG로 근거를 찾는 데서 멈추지 않고, 그 근거가 결론을 실제로 지지하는지 검증해 금융 민원에서 위험한 자동 판단을 막는 안전 중심 분석 파이프라인입니다.
