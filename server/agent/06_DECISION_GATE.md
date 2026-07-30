# Decision Gate Rules

## 역할

Policy Gate는 LLM 에이전트가 아니라 일반 코드다. Evidence & Decision Agent의 검증 결과와 개인정보·고위험 신호를 받아 최종 진행 상태를 결정한다.

## 상태 규칙

```text
hold    명의도용·보이스피싱·사기 의심 또는 중대한 사실 충돌
amend   개인정보 마스킹·입력·증빙 보완이 먼저 필요
ask     핵심 사실 또는 조회 동의가 부족함
proceed 필요한 사실과 검증된 근거가 충분함
```

우선순위:

```text
hold > amend > ask > proceed
```

## 중요한 재질문 방지 규칙

다음 값은 `user_statements` 또는 `my_info_facts`에 있으면 다시 질문하지 않는다.

```text
expected_interest
actual_interest
principal
applied_rate
maturity_date
notice_received
```

이미 입력된 사실과 계산 결과가 있으면 리포트를 생성하고, 추가 질문은 실제로 결론에 필요한 누락값에 한정한다.

## `ask` 조건

- 내 금융정보 조회 동의가 없음
- 계좌·상품 연결이 모호함
- 예치기간·실제 지급액처럼 판단에 필수인 값이 없음
- 같은 금액이 원금인지 이자인지 의미가 불명확함
- 사용자 진술과 내 금융정보 중 어느 쪽이 맞는지 확인이 필요함

## `hold` 조건

- 명의도용·본인 미신청 거래·보이스피싱 의심
- 계약·거래·안내 기록이 중대한 값에서 충돌함
- 법적 책임이나 고액 배상 판단을 직접 요구함
- 검증되지 않은 근거로 결론을 확정해야 하는 상황

단순한 RAG 검색 후보 부족은 자동 hold가 아니다. `evidence_insufficient`와 함께 ask 또는 보류 사유를 설명한다.

## 출력 예시

```json
{
  "control": "proceed",
  "reasons": [
    "사용자 예상액과 실제 지급액이 모두 확인됨",
    "내 금융정보 거래내역과 계산 결과를 비교함",
    "약관·상품설명서 근거가 검증됨"
  ],
  "required_inputs": [],
  "human_review": false
}
```
