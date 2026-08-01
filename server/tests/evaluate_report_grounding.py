"""Response 리포트 품질(근거 grounding) 평가: 실제 리포트가 근거를 지어내지 않는지 확인.

report_composer.py는 LLM이 반환한 used_evidence_chunk_ids를 실제 evidence_refs에
있는 chunk_id로만 걸러낸다(78번째 줄 부근). 이 평가는 그 안전장치가 코드로만
존재하는 게 아니라 실제 파이프라인 실행에서도 항상 성립하는지 확인하고, 리포트
필수 항목 누락·결정 상태 불일치처럼 grounding과 직결된 구조적 결함도 함께 본다.
LLM이 시도했다가 걸러진(가짜) chunk_id의 원 비율은 필터 이후 상태만 관찰 가능해
측정하지 못한다는 점은 한계로 남긴다.

실행:
    python -m server.tests.evaluate_report_grounding
"""
from __future__ import annotations

import os

os.environ["SUPABASE_PERSISTENCE"] = "false"

from fastapi.testclient import TestClient

from server.app import app, get_index


PROMPTS = [
    "예금 만기 이자로 30만원을 예상했지만 실제로는 279,180원만 입금됐습니다. 가입금액은 1,000만원이고 적용금리는 3.3%였습니다.",
    "적금 자동이체가 한 번 실패해서 우대금리가 빠졌는데 그런 안내를 전혀 받지 못했습니다.",
    "신용대출 금리가 갑자기 올랐는데 사전 안내를 못 받았습니다.",
    "펀드 환매를 신청했는데 지급이 계속 지연되고 있습니다.",
    "저도 모르는 사이에 제 명의로 대출이 실행됐어요, 신청한 적이 없습니다.",
]

REQUIRED_NONEMPTY = ("complaint_content", "processing_result")


def main() -> None:
    get_index()
    client = TestClient(app)

    total_issues = 0
    grounded = 0
    fabricated: list[tuple[str, str, str]] = []
    missing_fields: list[tuple[str, str]] = []
    decision_mismatch: list[tuple[str, str, str]] = []

    for prompt in PROMPTS:
        response = client.post("/api/v1/cases/analyze", json={"prompt": prompt, "customer_id": "CUST-001"})
        body = response.json()
        for issue in body["issues"]:
            total_issues += 1
            evidence_ids = {ref["chunk_id"] for ref in issue["evidence_refs"]}
            report = issue["report"]
            cited = set(report.get("used_evidence_chunk_ids") or [])
            extra = cited - evidence_ids
            if extra:
                fabricated.append((issue["issue_id"], prompt[:40], str(extra)))
            else:
                grounded += 1

            for field in REQUIRED_NONEMPTY:
                if not str(report.get(field) or "").strip():
                    missing_fields.append((issue["issue_id"], field))

            expected_label = {"proceed": "진행", "ask": "추가 확인 필요", "amend": "보완 필요", "hold": "검토 대기"}
            control = issue["decision"]["control"]
            if report.get("current_decision") and report["current_decision"] != expected_label.get(control):
                decision_mismatch.append((issue["issue_id"], control, report.get("current_decision")))

    print(f"근거 subset 검증: {grounded}/{total_issues}건이 evidence_refs 안에서만 인용")
    for issue_id, prompt, extra in fabricated:
        print(f"  위반: {issue_id} ({prompt}) -> 없는 chunk_id 인용: {extra}")

    print(f"\n필수 필드 누락: {len(missing_fields)}건")
    for issue_id, field in missing_fields:
        print(f"  {issue_id}: {field} 비어있음")

    print(f"\ncurrent_decision 라벨 불일치: {len(decision_mismatch)}건")
    for issue_id, control, label in decision_mismatch:
        print(f"  {issue_id}: control={control}인데 라벨={label!r}")


if __name__ == "__main__":
    main()
