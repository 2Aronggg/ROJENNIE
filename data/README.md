# 금융 소비자 보호 데이터

```text
data/
├─ regulations/                         # 법령·공통 규정·법령 API 원문
│  └─ law_api/
├─ products/                            # 상품 약관·설명서·금리표
│  ├─ deposit/                          # 예금
│  ├─ savings/                          # 적금
│  ├─ loan/                             # 대출
│  ├─ rates/                            # 지급금리·금리 조견표
│  ├─ fund/                             # 펀드·ELS
│  └─ isa/                              # ISA
├─ cases/                                # 판례·분쟁조정 사례 원문
├─ complaints/                          # 통합 상담·라벨링 데이터
│  └─ aihub_25_finance_consulting/
├─ dictionary/                           # 금융 용어 사전
├─ corpus/                               # 런타임 RAG corpus
│  ├─ regulations.jsonl
│  ├─ products.jsonl
│  ├─ cases.jsonl
│  ├─ glossary.jsonl
│  └─ all.jsonl
└─ evaluation/                           # 민원 테스트셋
```

## RAG 사용 범위

- `corpus/regulations.jsonl`, `corpus/products.jsonl`, `corpus/cases.jsonl`이 판단 근거입니다.
- 규정·상품·판례는 목적별로 분리하되 `corpus/all.jsonl`로 합쳐 서버 검색기가 읽습니다.
- `complaints/`의 상담 JSON은 Issue Splitter·질문 흐름 개선용이며 RAG 근거로 사용하지 않습니다.
- `cases/`의 HWP는 `cases/cases.csv`로 추출해 판례 corpus에 포함합니다.
- `corpus/glossary.jsonl`과 `dictionary/`는 금융 용어를 쉬운 말로 설명하는 용도이며 판단 근거로 확정하지 않습니다.
- `evaluation/`은 회귀 테스트용입니다.

## 생성·갱신

```powershell
\.venv\Scripts\python.exe -m server.rag.ingest --data-dir data --output server/rag/chunks.jsonl
\.venv\Scripts\python.exe -m server.rag.build_corpus --data-dir data --chunks server/rag/chunks.jsonl --output-dir data/corpus
```

`server/rag/chunks.jsonl`은 원천 PDF·법령 API의 중간 산출물이고, 서버 런타임 검색은 `data/corpus/all.jsonl`을 사용합니다. corpus에는 현재 임베딩을 생성하지 않고 기존 full-text 검색과 선택적 vector 필드를 사용할 수 있게 보관합니다. 별도 CSV export는 유지하지 않습니다.
