"""Decision Gate 정확도 평가: 전체 파이프라인을 실제로 태워서 확인한다.

server/tests/test_decision_gate.py는 apply_decision_gate() 함수 자체를
손으로 만든 IssueAnalysis로 단위 테스트한다 - 게이트의 내부 로직이 스스로
의도한 대로 도는지 검증하는 것으로, 이미 있는 회귀 테스트다.

여기서는 다르게, Case Builder -> Evidence & Decision -> Decision Gate
전체 파이프라인에 실제 민원 문장을 태워서, 최종 control 상태가 상식적으로
맞는 상태인지 확인한다. 정답은 게이트 코드를 다시 베낀 게 아니라 "이런
상황이면 사람이 봐도 이 상태가 나와야 한다"는 시나리오 설계로 정한다
(예: 명의도용 언급 -> 반드시 hold, 계좌번호 원문 노출 -> 반드시 amend).

실행:
    python -m server.tests.evaluate_decision_gate
"""
from __future__ import annotations

import json
import os

# SupabaseStore.enabled normally checks "unittest" in sys.modules to stay off
# during tests; this script calls the real /analyze endpoint outside unittest,
# so without this it would write every scenario into the live Supabase project.
os.environ["SUPABASE_PERSISTENCE"] = "false"

from fastapi.testclient import TestClient

from server.app import app, get_index


SCENARIOS = [
    (
        "예금 만기 이자로 30만원을 예상했지만 실제로는 279,180원만 입금됐습니다. "
        "가입금액은 1,000만원이고 적용금리는 3.3%였습니다.",
        "proceed",
        "MCP 계약·거래내역과 사용자 진술이 모두 있어 확정 판단 가능",
    ),
    (
        "적금 자동이체가 한 번 실패해서 우대금리가 빠졌는데 그런 안내를 전혀 받지 못했습니다.",
        "proceed",
        "MCP 이력에 자동이체 실패·안내 부재 기록이 그대로 있음",
    ),
    (
        "신용대출 금리가 갑자기 올랐는데 사전 안내를 못 받았습니다.",
        "proceed",
        "MCP 금리 변경 이력에서 기존/변경 금리와 안내 여부를 모두 확인 가능",
    ),
    (
        "펀드 환매를 신청했는데 지급이 계속 지연되고 있습니다.",
        "ask",
        "가상 계좌 데이터가 없는 상품이라 신청일 등 핵심 사실을 되물어야 함",
    ),
    (
        "저도 모르는 사이에 제 명의로 대출이 실행됐어요, 신청한 적이 없습니다.",
        "hold",
        "명의도용은 어떤 조건에서도 자동 확정하지 않는 안전 규칙",
    ),
    (
        "제 계좌 123-456-789012에서 돈이 이상하게 빠져나갔어요, 확인해주세요.",
        "amend",
        "민원 원문에 계좌번호가 그대로 노출되어 마스킹·범위 확인이 필요",
    ),
]


def main() -> None:
    get_index()  # 인덱스 빌드 시간을 결과 밖으로
    client = TestClient(app)
    correct = 0
    for prompt, expected, rationale in SCENARIOS:
        response = client.post("/api/v1/cases/analyze", json={"prompt": prompt, "customer_id": "CUST-001"})
        body = response.json()
        controls = [issue["decision"]["control"] for issue in body["issues"]]
        actual = controls[0] if controls else "미분류"
        ok = actual == expected
        correct += ok
        mark = "OK" if ok else "MISS"
        print(f"[{mark}] 기대={expected} 실제={actual} | {rationale}")
        if not ok:
            print(f"       프롬프트: {prompt[:60]}")
            print(f"       전체 이슈: {json.dumps(controls, ensure_ascii=False)}")

    print(f"\n정확도: {correct}/{len(SCENARIOS)} = {correct/len(SCENARIOS):.1%}")


if __name__ == "__main__":
    main()
