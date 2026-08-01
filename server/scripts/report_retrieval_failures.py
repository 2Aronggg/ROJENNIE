"""Print detailed RAG retrieval misses for the hand-labeled evaluation set.

This script reuses the CASES/PRODUCTS query sets from
server.tests.evaluate_retrieval, but unlike the recall-only evaluator it prints
the actual top-k documents returned for every miss.

Usage:
    python -m server.scripts.report_retrieval_failures --top-k 5
    python -m server.scripts.report_retrieval_failures --top-k 10 --out data/corpus/retrieval-failures.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from server.rag.embeddings import embed_query
from server.rag.retrieval import SearchIndex
from server.tests.evaluate_retrieval import CASES, PRODUCTS


def _preview(text: str, limit: int = 180) -> str:
    return " ".join(text.split())[:limit]


def _result_dict(result: Any, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "doc_id": result.doc_id,
        "chunk_id": result.chunk_id,
        "doc_type": _doc_type_from_path(result.path),
        "path": result.path,
        "page": result.page,
        "section": result.section,
        "score": result.score,
        "match_type": result.match_type,
        "effective_from": result.effective_from.isoformat() if result.effective_from else None,
        "effective_to": result.effective_to.isoformat() if result.effective_to else None,
        "snippet": _preview(result.snippet),
    }


def _doc_type_from_path(path: str) -> str:
    normalized = path.split(":", 1)[-1].replace("\\", "/")
    if normalized.startswith("cases/"):
        return "case"
    if normalized.startswith("products/"):
        return "product"
    if normalized.startswith(("regulations/", "공통규정/")):
        return "regulation"
    if normalized.startswith("dictionary/"):
        return "glossary"
    return "unknown"


def analyze_items(
    index: SearchIndex,
    label: str,
    items: list[tuple[str, str]],
    *,
    top_k: int,
    use_hybrid: bool,
) -> dict[str, Any]:
    hits = 0
    misses: list[dict[str, Any]] = []

    for query, expected_doc_id in items:
        vector = embed_query(query) if use_hybrid else None
        results = index.search(query, as_of=date.today(), top_k=top_k, query_embedding=vector)
        found_rank = next((rank for rank, result in enumerate(results, start=1) if result.doc_id == expected_doc_id), None)
        if found_rank is not None:
            hits += 1
            continue

        misses.append(
            {
                "label": label,
                "query": query,
                "expected_doc_id": expected_doc_id,
                "top_results": [_result_dict(result, rank) for rank, result in enumerate(results, start=1)],
            }
        )

    return {
        "label": label,
        "n": len(items),
        "hits": hits,
        "misses": len(misses),
        "recall": hits / len(items) if items else 0.0,
        "miss_details": misses,
    }


def print_report(report: dict[str, Any], *, max_misses: int) -> None:
    print(f"mode: {report['mode']}, top_k={report['top_k']}")
    print(f"index_source: {report['index_source']}")
    for section in report["sections"]:
        print(f"\n[{section['label']}] recall@{report['top_k']}: {section['hits']}/{section['n']} = {section['recall']:.1%}")
        for miss in section["miss_details"][:max_misses]:
            print(f"\nMISS query: {miss['query']}")
            print(f"expected_doc_id: {miss['expected_doc_id']}")
            if not miss["top_results"]:
                print("  top results: (none)")
                continue
            for result in miss["top_results"]:
                print(
                    "  "
                    f"#{result['rank']} doc={result['doc_id']} chunk={result['chunk_id']} "
                    f"type={result['doc_type']} score={result['score']} match={result['match_type']}"
                )
                print(f"     section={result['section']} page={result['page']}")
                print(f"     path={result['path']}")
                print(f"     snippet={result['snippet']}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=Path("data/corpus/all.jsonl"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-misses", type=int, default=8)
    args = parser.parse_args()

    index = SearchIndex.from_data_dir(
        Path("data"),
        chunks_path=args.chunks,
        exclude_doc_types=frozenset({"glossary"}),
    )
    sections = [
        analyze_items(index, "cases", CASES, top_k=args.top_k, use_hybrid=args.hybrid),
        analyze_items(index, "products", PRODUCTS, top_k=args.top_k, use_hybrid=args.hybrid),
    ]
    total_n = sum(section["n"] for section in sections)
    total_hits = sum(section["hits"] for section in sections)
    report = {
        "mode": "hybrid" if args.hybrid else "text-only",
        "top_k": args.top_k,
        "chunks": str(args.chunks),
        "index_source": index.source,
        "total": {
            "n": total_n,
            "hits": total_hits,
            "misses": total_n - total_hits,
            "recall": total_hits / total_n if total_n else 0.0,
        },
        "sections": sections,
    }

    print_report(report, max_misses=args.max_misses)
    print(f"\n[total] recall@{args.top_k}: {total_hits}/{total_n} = {report['total']['recall']:.1%}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote JSON report: {args.out}")


if __name__ == "__main__":
    main()
