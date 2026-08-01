"""End-to-end service evaluator for the non-UI KB Key Buddy pipeline.

Runs rule-based issue splitting, focal/fact extraction, local RAG retrieval, and
the decision gate without external LLM or MCP calls. The goal is submission-time
regression visibility, not optimistic benchmarking.

Usage:
    python -m server.scripts.evaluate_service_pipeline
    python -m server.scripts.evaluate_service_pipeline --out data/evaluation/eval_results.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from server.agents.decision_gate import CONTROL_PRIORITY, apply_decision_gate
from server.agents.facts import missing_facts, resolve_facts
from server.agents.rag_query import build_rag_query
from server.agents.router import split_prompt_to_issues
from server.rag.retrieval import SearchIndex
from server.schemas import Decision, IssueAnalysis


DATASET_PATH = Path("data/evaluation/service_eval_dataset.json")
CANONICAL_PATH = Path("data/corpus/canonical_doc_ids.json")
DEFAULT_OUT = Path("data/evaluation/eval_results.json")


@dataclass
class PipelineIssue:
    issue_id: str
    product: str
    issue_type: str
    status: str
    missing_facts: list[str]
    evidence_doc_ids: list[str]
    evidence_chunk_ids: list[str]
    risk_flags: list[str]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = _load_json(path)
    return {str(key): str(value) for key, value in payload.get("canonical_by_doc_id", {}).items()}


def _canonical(doc_id: str, mapping: dict[str, str]) -> str:
    seen: set[str] = set()
    current = doc_id
    while current in mapping and current not in seen:
        seen.add(current)
        current = mapping[current]
    return current


def _status_match(actual: list[str], expected: list[str]) -> bool:
    if len(actual) != len(expected):
        return False
    return all(left == right for left, right in zip(actual, expected))


def _status_at_least_as_safe(actual: str, expected: str) -> bool:
    return CONTROL_PRIORITY.get(actual, -1) >= CONTROL_PRIORITY.get(expected, -1)


def _contains_any(values: list[str], expected: list[str]) -> bool:
    if not expected:
        return True
    compact_values = " ".join(values)
    return any(item in compact_values for item in expected)


def _analyze_prompt(index: SearchIndex, prompt: str, *, as_of: date) -> list[PipelineIssue]:
    routed = split_prompt_to_issues(prompt, use_llm=False)
    issues: list[PipelineIssue] = []
    for issue in routed:
        resolution = resolve_facts(issue.facts)
        missing = missing_facts(issue.required_facts, resolution)
        rag_query = build_rag_query(issue, use_llm=False)
        evidence = index.search_many(
            rag_query.variants or [rag_query.text],
            product=issue.product,
            as_of=as_of,
            top_k=5,
        )
        risk_flags: list[str] = []
        if missing:
            risk_flags.append("missing_facts")
        if resolution.conflicts:
            risk_flags.append("fact_conflict")
        if not evidence:
            risk_flags.append("evidence_insufficient")
        lowered = issue.text.lower()
        if any(signal in issue.text for signal in ("명의도용", "모르는 대출", "승인하지 않은", "보이스피싱")):
            risk_flags.append("identity_theft")
        if any(signal in lowered for signal in ("ignore previous", "system prompt", "you are now")) or "이전 지시를 무시" in issue.text:
            risk_flags.append("suspicious_input")

        baseline = "ask" if missing or not evidence or resolution.conflicts else "proceed"
        analysis = IssueAnalysis(
            issue_id=issue.issue_id,
            product=issue.product,
            issue_type=issue.issue_type,
            routing_confidence=issue.routing_confidence,
            routing_method=issue.routing_method,
            focal=issue.focal,
            target=issue.target,
            mock_data={},
            facts=issue.facts,
            missing_facts=list(dict.fromkeys(missing)),
            fact_resolution=resolution,
            retrieval_query=rag_query.text,
            evidence_refs=evidence,
            decision=Decision(control=baseline, risk_flags=risk_flags),
            risk_level="low",
            risk_reasons=[],
            content_scope={"mode": "summary", "requires_user_confirmation": False},
            next_steps=[],
        )
        gate = apply_decision_gate(analysis)
        issues.append(
            PipelineIssue(
                issue_id=issue.issue_id,
                product=issue.product,
                issue_type=issue.issue_type,
                status=gate.control,
                missing_facts=list(dict.fromkeys(missing)),
                evidence_doc_ids=[ref.doc_id for ref in evidence],
                evidence_chunk_ids=[ref.chunk_id for ref in evidence],
                risk_flags=risk_flags,
            )
        )
    return issues


def evaluate(dataset_path: Path, *, chunks_path: Path, canonical_path: Path) -> dict[str, Any]:
    dataset = _load_json(dataset_path)
    canonical = _canonical_map(canonical_path)
    index = SearchIndex.from_data_dir(Path("data"), chunks_path=chunks_path, exclude_doc_types=frozenset({"glossary"}))

    cases = dataset["cases"]
    totals = Counter()
    by_category: dict[str, Counter] = defaultdict(Counter)
    status_confusion: dict[str, Counter] = defaultdict(Counter)
    failures: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for item in cases:
        predicted = _analyze_prompt(index, item["prompt"], as_of=date.today())
        predicted_statuses = [issue.status for issue in predicted]
        expected_statuses = list(item.get("expected_status") or [])
        predicted_docs = sorted({_canonical(doc_id, canonical) for issue in predicted for doc_id in issue.evidence_doc_ids})
        expected_docs = sorted({_canonical(doc_id, canonical) for doc_id in item.get("expected_focal_docs", [])})
        predicted_missing = [field for issue in predicted for field in issue.missing_facts]
        expected_missing = list(item.get("expected_missing_info") or [])

        issue_count_ok = len(predicted) == int(item["expected_issue_count"])
        status_exact_ok = _status_match(predicted_statuses, expected_statuses)
        status_safe_ok = len(predicted_statuses) == len(expected_statuses) and all(
            _status_at_least_as_safe(actual, expected) for actual, expected in zip(predicted_statuses, expected_statuses)
        )
        evidence_ok = all(doc_id in predicted_docs for doc_id in expected_docs)
        missing_ok = _contains_any(predicted_missing, expected_missing)

        checks = {
            "issue_count": issue_count_ok,
            "status_exact": status_exact_ok,
            "status_safe": status_safe_ok,
            "evidence": evidence_ok,
            "missing_info": missing_ok,
        }
        for key, ok in checks.items():
            totals[key] += int(ok)
            by_category[item["category"]][key] += int(ok)
        totals["cases"] += 1
        by_category[item["category"]]["cases"] += 1
        for expected, actual in zip(expected_statuses, predicted_statuses):
            status_confusion[expected][actual] += 1

        record = {
            "case_id": item["case_id"],
            "category": item["category"],
            "expected_issue_count": item["expected_issue_count"],
            "predicted_issue_count": len(predicted),
            "expected_status": expected_statuses,
            "predicted_status": predicted_statuses,
            "expected_focal_docs": expected_docs,
            "predicted_canonical_docs": predicted_docs,
            "expected_missing_info": expected_missing,
            "predicted_missing_facts": predicted_missing,
            "checks": checks,
            "issues": [issue.__dict__ for issue in predicted],
        }
        records.append(record)
        if not all(checks.values()):
            failures.append(record)

    n = totals["cases"] or 1
    summary = {
        "cases": totals["cases"],
        "issue_count_accuracy": totals["issue_count"] / n,
        "status_exact_accuracy": totals["status_exact"] / n,
        "status_safety_accuracy": totals["status_safe"] / n,
        "evidence_recall_case_level": totals["evidence"] / n,
        "missing_info_coverage": totals["missing_info"] / n,
    }
    category_summary = {
        category: {
            "cases": counts["cases"],
            "issue_count_accuracy": counts["issue_count"] / counts["cases"],
            "status_exact_accuracy": counts["status_exact"] / counts["cases"],
            "status_safety_accuracy": counts["status_safe"] / counts["cases"],
            "evidence_recall_case_level": counts["evidence"] / counts["cases"],
            "missing_info_coverage": counts["missing_info"] / counts["cases"],
        }
        for category, counts in sorted(by_category.items())
    }
    return {
        "dataset": str(dataset_path),
        "index_source": index.source,
        "summary": summary,
        "by_category": category_summary,
        "status_confusion": {expected: dict(actuals) for expected, actuals in status_confusion.items()},
        "failures": failures,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--chunks", type=Path, default=Path("data/corpus/all.jsonl"))
    parser.add_argument("--canonical", type=Path, default=CANONICAL_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = evaluate(args.dataset, chunks_path=args.chunks, canonical_path=args.canonical)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
