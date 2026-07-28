# Logic Verification Rules

## 목적

검색된 규정·약관·사례를 사건의 확인된 사실에 적용하고, 무엇이 확인되었고 무엇이 부족한지 설명한다.

## 검증 순서

1. 적용 문서의 시행일 확인
2. 적용 대상 상품·계약 확인
3. 요건 목록 작성
4. 각 요건과 사실·증빙 연결
5. 예외·제외 조건 확인
6. 유사 사례와 다른 사실 확인
7. 소비자에게 필요한 다음 단계 산출

## 판단 상태

```text
supported   요건과 사실·증빙이 연결됨
unsupported 확인된 사실이 요건을 충족하지 않음
unknown     핵심 사실·증빙이 부족함
conflict    문서·사실·답변 사이에 충돌이 있음
```

`unknown`을 `unsupported`로 바꾸지 않는다. 증거가 부족하다는 이유만으로 소비자에게 불리한 결론을 내리지 않는다.

## 출력

```json
{
  "finding": "unknown",
  "conditions": [
    {
      "condition": "사전 안내 여부",
      "fact_refs": [],
      "evidence_refs": [],
      "status": "missing"
    }
  ],
  "exceptions": [],
  "counterpoints": [],
  "recommended_control": "ask"
}
```

승소 가능성, 환급 금액, 법적 책임을 확정적으로 예측하지 않는다.
