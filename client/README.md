# Client

금융소비자 보호 에이전트의 사용자 화면 영역입니다.

## MVP 화면

### 1. 복합 문의 입력 및 파일 첨부
- 자유 텍스트 입력. 여러 민원이 섞여 있어도 그대로 입력해도 된다는 걸 placeholder 문구로 안내한다.
- 첨부: 안내문, 계약서, 스크린샷(이미지/PDF).
- 제출 → `POST /api/v1/cases/analyze` 호출 → `case_id` 수신 즉시 "분석 중" 화면(2번)으로 전환.
- 계좌번호·주민번호 등 민감정보를 입력창에 직접 치면(Shared Rules 규칙 7) 클라이언트단에서도 1차로 "이 창에는 계좌번호·주민번호를 입력하지 마세요" 경고를 즉시 띄운다. 서버 검증을 기다리지 않는다.

### 2. 민원별 분해 결과 카드
- Issue Splitter가 나눈 `issue_id` 단위로 카드 1개씩 렌더링. 한 카드에 두 issue를 섞지 않는다(원칙 1번).
- 카드 헤더: 자동 생성된 이슈 제목 + 상품군 배지(예금/적금/대출/펀드 등).
- 카드 바디: `status` 배지(proceed/amend/ask/hold) + `reasons` 1~2줄 요약.
- 카드 클릭 → 3·4·5번 화면(해당 issue의 상세)으로 진입.

### 3. 사건 그래프 또는 처리 단계 상태
두 방식 중 하나(또는 단계적 확장):
- **(a) 그래프 뷰**: Case Graph Schema v1의 노드(Contract/Notice/Institution/MonetaryAmount/CompanyResponse/Evidence)를 시각화. `Fact` 노드는 별도 노드로 안 그리고, 값이 붙은 노드 속성 옆에 "출처 보기" 아이콘으로만 표시.
- **(b) 처리 단계 뷰**: 9단계 파이프라인(Issue Splitter → … → Response Composer) 중 현재 어디까지 처리됐는지 진행 바.
- MVP 데모 시점엔 (b)가 구현 부담이 훨씬 적다 — (a)는 스트레치 목표로 표시 추천.

### 4. 규정·약관 근거 상세 패널
- `evidence_refs` 배열을 리스트로 렌더링. 각 항목: `source_type` 배지 + `title` + `article` + `effective_date`.
- `similarity_score`는 원 점수를 그대로 노출하지 않고 "관련도 높음/보통" 2~3단계로 변환해서 보여준다(원칙 추가 항목 참고).
- 항목 클릭 → 해당 조항 위치로 스크롤/팝업. `snippet`은 이미 200자 제한이라 "전체 보기"는 두지 않고, 출처 문서 링크만 제공한다.

### 5. 누락 정보·제출 서류 체크리스트
- `status: ask`일 때 `required_inputs` 배열을 체크리스트로 렌더링(`field` + `reason`).
- `amend`(마스킹/서류 정리 필요)는 개념이 다르므로 같은 화면에서도 섹션을 분리해서 절대 섞지 않는다.
- 사용자가 입력을 채운 뒤 재분석을 요청하는 흐름(재호출 API)은 아직 정의 안 됨.

### 6. `proceed / amend / ask / hold` 상태 표시
- 색상·아이콘 고정 매핑(디자인 통일용 제안): proceed=초록/체크, amend=파랑/편집, ask=노랑/물음표, hold=보라(또는 회색)/방패. **빨강은 쓰지 않는다** — hold를 오류처럼 보이지 않게 한다는 원칙과 직결.
- `warnings`에 `level: critical`이 있으면 hold와 함께 사유를 순화해서("전문가 검토가 필요합니다") 노출한다. `code`(예: `FRAUD_SUSPECTED`) 값은 절대 화면에 그대로 노출하지 않는다.

### 7. Human Review 대기 상태
- hold된 issue에 대해 "지금 자동 판단하지 않고 사람이 확인 중"임을 알리는 화면.
- 예상 소요시간처럼 확정 안 된 정보는 표시하지 않는다(근거 없는 안심 표현 금지 원칙과 동일선상).


## API 계약

### `POST /api/v1/cases/analyze`
```json
// Request
{
  "message": "복합 문의 원문",
  "attachments": [
    { "filename": "notice.pdf", "file_ref": "upload_id 또는 presigned_url" }
  ]
}
```
```json
// Response (202)
{ "case_id": "case_001", "status": "processing" }
```
### `GET /api/v1/cases/{case_id}`
```json
{
  "case_id": "case_001",
  "overall_status": "ask",
  "issues": [
    {
      "issue_id": "issue_001_a",
      "status": "proceed",
      "reasons": ["..."],
      "verified_facts": [],
      "evidence_refs": [],
      "warnings": [],
      "masked_fields": []
    },
    {
      "issue_id": "issue_001_b",
      "status": "ask",
      "required_inputs": [
        { "field": "notice_received_date", "reason": "금리 변경 안내를 받으신 날짜를 알려주세요" }
      ]
    }
  ],
  "created_at": "2026-07-28T09:12:00+09:00",
  "updated_at": "2026-07-28T09:20:00+09:00"
}
```
- `issues` 배열의 각 항목은 서버가 이미 정의한 `AgentOutput` 스키마를 그대로 사용한다. Client는 필드를 새로 정의하지 않고 그대로 소비한다.
- `overall_status`는 issue들 중 가장 보수적인 상태 우선(`hold > ask > amend > proceed`)으로 계산한다.

### `POST /api/v1/cases/{case_id}/review`
```json
// Request
{
  "issue_id": "issue_001_b",
  "decision": "approve | reject | request_more_info",
  "reviewer_note": "string"
}
```

화면은 모델의 자유 형식 텍스트를 직접 파싱하지 않고, server가 반환하는 구조화된 case schema(`AgentOutput`)를 사용합니다.




## 원칙

- 민원별 결과를 한 카드에 섞지 않는다.
- 근거 문서의 페이지·조항을 클릭해서 볼 수 있게 한다.
- 개인정보 원문은 기본적으로 표시하지 않는다. `masked_fields`는 "일부 정보가 보호 처리됨" 정도로만 안내한다.
- `hold`를 오류처럼 보이지 않게 하고 검토 사유와 다음 단계를 표시한다. 내부 경고 코드는 그대로 노출하지 않는다.
- 확정적 표현("위법이다", "반드시 환급된다")이나 근거 없는 안심 표현은 화면 문구에도 쓰지 않는다.
- 모든 상세 화면 하단에 고정 문구를 노출한다: "본 안내는 참고용 정보이며, 최종 판단은 금융감독원 분쟁조정 등 정식 절차를 통해 결정됩니다."
- `similarity_score`, warning `code` 같은 내부 전용 필드는 사용자용 표현으로 변환해서만 노출하고 원값은 노출하지 않는다.

현재는 UI 코드 없이 화면·API 계약만 정의되어 있습니다.
`