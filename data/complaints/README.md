# Complaints

AI Hub `25. 금융분야 고객상담 데이터`를 통합해 보관합니다.

- `aihub_25_finance_consulting/complaints.jsonl`: 원천 상담과 연결된 라벨을 합친 민원 데이터
- 민원 표현·Issue Splitter 평가에 사용합니다.
- 법령·약관 판단 근거로는 사용하지 않습니다.
- 현재 ingest는 PDF와 `regulations/law_api/*.json`만 RAG에 넣으므로 상담 JSONL은 자동 색인하지 않습니다.
