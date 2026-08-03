"""End-to-end Decision Gate scenario check.

This script is not a unit test. It sends realistic prompts through
POST /api/v1/cases/analyze and verifies the final user-facing control.

After the Evidence-Conclusion Audit Layer was introduced, a scenario can be
downgraded from ``proceed`` to ``ask`` even when mock bank data exists. That is
intentional when Logic Verification marks the support chain as unverified or
when direct evidence is still insufficient.

Run:
    python -m server.tests.evaluate_decision_gate
"""

from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from server.app import app, get_index


os.environ["SUPABASE_PERSISTENCE"] = "false"


SCENARIOS = [
    {
        "prompt": (
            "예금 만기 이자로 30만원을 예상했지만 실제로는 279,180원만 입금됐습니다. "
            "가입금액은 1,000만원이고 적용금리는 3.3%였습니다."
        ),
        "expected": "proceed",
        "rationale": (
            "mock 원장의 세전이자 330,000 - 세금 50,820 = 279,180이 사용자 진술과 "
            "정확히 일치해 계산 조건이 닫힌다. 감사 레이어도 support_chain을 "
            "direct_match/direct_evidence로 판정하고 missing_facts가 비어 있다. "
            "(만료 법령을 corpus에서 제외하기 전에는 직접 근거가 안 잡혀 ask로 "
            "강등됐고, 그 시점 동작에 맞춰 기대값이 ask로 적혀 있었다.)"
        ),
    },
    {
        "prompt": "적금 자동이체가 두 번 실패해서 우대금리가 빠졌는데 그런 안내를 전혀 받지 못했습니다.",
        "expected": "proceed",
        "rationale": "mock 이력에서 자동이체 실패와 안내 부재 기록을 확인할 수 있다.",
    },
    {
        "prompt": "신용대출 금리가 갑자기 올랐는데 사전 안내를 못 받았습니다.",
        "expected": "ask",
        "rationale": (
            "LLM/logic verification이 근거 사슬을 unverified로 판정하면 "
            "직접 결론을 내지 않고 ask로 강등한다."
        ),
    },
    {
        "prompt": "대출 상환을 신청했는데 지급이 계속 지연되고 있습니다.",
        "expected": "ask",
        "rationale": "mock 계좌 데이터가 없는 상품/사안은 신청일 등 핵심 사실을 되물어야 한다.",
    },
    {
        "prompt": "저도 모르는 사이에 명의로 대출이 실행됐어요. 신청한 적이 없습니다.",
        "expected": "hold",
        "rationale": "명의도용은 어떤 조건에서도 자동 확정하지 않는 안전 규칙이다.",
    },
    {
        "prompt": "제 계좌 123-456-789012에서 돈이 이상하게 빠져나갔어요, 확인해주세요.",
        "expected": "amend",
        "rationale": "민원 원문에 계좌번호가 노출되어 마스킹과 범위 확인이 필요하다.",
    },
]


def main() -> None:
    get_index()
    client = TestClient(app)
    correct = 0

    for scenario in SCENARIOS:
        response = client.post(
            "/api/v1/cases/analyze",
            json={"prompt": scenario["prompt"], "customer_id": "CUST-001"},
        )
        response.raise_for_status()
        body = response.json()
        controls = [issue["decision"]["control"] for issue in body["issues"]]
        actual = controls[0] if controls else "unclassified"
        expected = scenario["expected"]
        ok = actual == expected
        correct += int(ok)
        mark = "OK" if ok else "MISS"
        print(f"[{mark}] expected={expected} actual={actual} | {scenario['rationale']}")
        if not ok:
            print(f"       prompt: {scenario['prompt'][:80]}")
            print(f"       all issue controls: {json.dumps(controls, ensure_ascii=False)}")

    total = len(SCENARIOS)
    print(f"\naccuracy: {correct}/{total} = {correct / total:.1%}")


if __name__ == "__main__":
    main()
