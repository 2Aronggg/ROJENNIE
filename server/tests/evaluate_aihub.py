"""AIHub 실제 상담 데이터로 라우터 상품 분류를 검증한다.

이 파일은 자동 회귀 테스트(pytest/unittest)가 아니라 독립 실행 스크립트다.
data/complaints/aihub_25_finance_consulting/complaints.jsonl은 자체 제작이 아닌
외부 실데이터(하나은행 상담 전문)라서, 자체 제작 평가셋(data/evaluation/*.json)과
구분해 별도로 실행한다.

30,156건 중 실제로 "민원" 상황(consulting_situation == 민원응대)은 2,069건뿐이고,
그중에서도 qa_topic만으로 상품(예금/적금/대출)을 모호함 없이 판별할 수 있는 건
"대출문의(만기/연장/조회등)" 하나뿐이다. 나머지 topic(거래내역조회, 자동이체조회,
금융거래한도 등)은 여러 상품에 걸쳐 있어 라벨을 임의로 붙이면 근거 없는 정답이
되므로 채점 대상에서 제외한다. issue_type 수준의 정답은 이 데이터에 없어 상품
분류만 검증한다.

실행:
    python -m server.tests.evaluate_aihub
    python -m server.tests.evaluate_aihub --llm --sample 30
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from server.agents.router import split_prompt_to_issues


DATA_PATH = Path("data/complaints/aihub_25_finance_consulting/complaints.jsonl")

# qa_topic -> product. Only topics that map to exactly one product without
# guessing from free text are included; everything else is excluded from
# scoring rather than force-labeled.
TOPIC_TO_PRODUCT = {
    "대출문의(만기/연장/조회등)": "대출",
}


def load_labeled_questions() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    with DATA_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            for label in row.get("labels", []):
                if label.get("consulting_situation") != "민원응대":
                    continue
                product = TOPIC_TO_PRODUCT.get(label.get("qa_topic"))
                if product is None:
                    continue
                question = (label.get("input") or {}).get("question", "").strip()
                if not question:
                    continue
                items.append({
                    "qa_id": label["qa_id"],
                    "qa_topic": label["qa_topic"],
                    "expected_product": product,
                    "text": question,
                })
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="use the real LLM router instead of the rule fallback")
    parser.add_argument("--sample", type=int, default=0, help="limit to first N items (0 = all)")
    args = parser.parse_args()

    items = load_labeled_questions()
    if args.sample:
        items = items[: args.sample]

    print(f"채점 대상: {len(items)}건 (민원응대 + 상품 명확 topic)")
    correct = 0
    confusions: Counter[tuple[str, str]] = Counter()
    for item in items:
        issues = split_prompt_to_issues(item["text"], use_llm=args.llm)
        predicted = issues[0].product if issues else "미분류"
        is_correct = predicted == item["expected_product"]
        correct += is_correct
        if not is_correct:
            confusions[(item["expected_product"], predicted)] += 1

    accuracy = correct / len(items) if items else 0.0
    print(f"정확도: {correct}/{len(items)} = {accuracy:.1%}")
    if confusions:
        print("오분류:")
        for (expected, predicted), count in confusions.most_common():
            print(f"  {expected} -> {predicted}: {count}건")


if __name__ == "__main__":
    main()
