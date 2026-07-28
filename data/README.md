# RAG 데이터 안내

## 현재 보유 데이터

| 경로 | 내용 | 수량 |
|---|---|---:|
| `공통규정/` | 금융소비자보호법, 은행법, 은행법 시행령, 자본시장법 | 4 PDF |
| `예금 상품 설명서/` | 예금·적금 약관 및 상품설명서 | 12 PDF |
| `펀드 상품 설명서/` | 펀드·ELS 투자설명서 | 10 PDF |
| `자체제작 민원/single_issue_75.json` | 단일 민원 | 75건 |
| `자체제작 민원/complex_issue_75.json` | 복합 민원 및 하위 민원 정답 | 75건 |
| `자체제작 민원/all_150.csv` | 단일·복합 민원 통합본 | 150건 |

## RAG에 넣을 문서와 넣지 않을 데이터

- PDF는 법령·약관·상품설명서 RAG 원문이다.
- JSON과 CSV는 검색 근거가 아니라 Issue Splitter 평가·회귀 테스트 데이터다.
- `complex_issue_75.json`의 `ground_truth_subissues`는 분해 평가에 사용한다.
- 자체 제작 민원 문장을 법령의 근거로 사용하지 않는다.

## 필수 메타데이터

각 chunk는 최소한 다음 정보를 가져야 한다.

```json
{
  "doc_id": "unique-id",
  "chunk_id": "unique-id-page-12",
  "path": "data/공통규정/example.pdf",
  "doc_type": "law|terms|product_manual|case",
  "product": ["공통"],
  "issue_types": ["설명의무위반"],
  "source": "official-source",
  "published_at": null,
  "effective_from": null,
  "effective_to": null,
  "page": 12,
  "section": "제X조",
  "text": "..."
}
```

## 주의사항

- 파일명만 보고 현행 법령으로 판단하지 않는다.
- 계약일·사건일·문서 작성일에 유효한 규정인지 확인한다.
- 현재 보험 문서와 공식 분쟁조정 사례 원문은 없다.
- 시행일이 미래인 문서는 해당 시행일 전 사건에 적용하지 않는다.
