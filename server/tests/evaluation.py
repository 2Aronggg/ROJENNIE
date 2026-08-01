from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"scenario file must contain a list: {path}")
    return data


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def expected_issue_keys(case: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(item["product"]), str(item["issue_type"]))
        for item in case.get("ground_truth_subissues", [])
    }


def predicted_issue_keys(issues: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (str(item.get("product", "")), str(item.get("issue_type", "")))
        for item in issues
    }


def score_split(
    expected_cases: list[dict[str, Any]],
    predictions: dict[str, list[dict[str, Any]]],
) -> dict[str, float | int]:
    """Score product/issue pairs; text-level scoring belongs to the B agent tests."""
    expected = [expected_issue_keys(case) for case in expected_cases]
    predicted = [predicted_issue_keys(predictions.get(str(case["id"]), [])) for case in expected_cases]
    exact = sum(actual == wanted for actual, wanted in zip(predicted, expected))
    true_positive = sum(len(actual & wanted) for actual, wanted in zip(predicted, expected))
    predicted_total = sum(len(items) for items in predicted)
    expected_total = sum(len(items) for items in expected)
    precision = true_positive / predicted_total if predicted_total else 0.0
    recall = true_positive / expected_total if expected_total else 0.0
    return {
        "cases": len(expected_cases),
        "exact_match": exact / len(expected_cases) if expected_cases else 0.0,
        "precision": precision,
        "recall": recall,
    }
