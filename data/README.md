# 금융 소비자 보호 데이터

```text
data/
├─ regulations/       # 법령·감독규정·공통 약관
├─ products/          # 예금·적금·펀드·ELS 상품 문서
│  ├─ deposit/
│  └─ fund/
├─ cases/             # 공개 분쟁조정·판례·처리결과
├─ complaints/        # 비식별 실제 상담·민원 표현
├─ dictionary/        # 금융 용어 사전
└─ evaluation/        # 자체 제작 민원 테스트셋
```

## 사용 원칙

- `regulations/`, `products/`, `cases/`는 RAG 판단 근거입니다.
- `complaints/`는 문의 분해와 상담 흐름 개선용이며, 법적 판단 근거가 아닙니다.
- `evaluation/`은 재현 가능한 회귀 테스트용이므로 실제 데이터로 교체하지 않습니다.
- `dictionary/`는 어려운 금융 용어를 쉽게 설명할 때 별도로 조회합니다.
- 대출 데이터와 실제 고객 개인정보는 저장하지 않습니다.

## 문서 메타데이터

PDF를 추가할 때는 파일명 또는 별도 메타데이터로 다음 정보를 확인할 수 있어야 합니다.

`source`, `published_at`, `effective_from`, `effective_to`, `product`, `issue_type`
