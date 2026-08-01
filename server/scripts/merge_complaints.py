from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _read_json(path: Path) -> tuple[Path, dict]:
    return path, json.loads(path.read_text(encoding="utf-8"))


def merge_complaints(input_dir: Path, output: Path) -> dict[str, int]:
    files = sorted(input_dir.rglob("*.json"))
    source_files = [path for path in files if any(part.startswith(("TS_", "VS_")) for part in path.parts)]
    label_files = [path for path in files if any(part.startswith(("TL_", "VL_")) for part in path.parts)]

    sources: dict[str, dict] = {}
    duplicate_source_ids: set[str] = set()
    conflicting_duplicate_ids: set[str] = set()
    with ThreadPoolExecutor(max_workers=12) as pool:
        for path, payload in pool.map(_read_json, source_files):
            source = payload.get("source", {})
            source_id = str(source.get("source_id") or "")
            if source_id:
                record = {
                    "case_id": source_id,
                    "source": source,
                    "consulting": payload.get("consulting", {}),
                    "labels": [],
                }
                if source_id in sources:
                    duplicate_source_ids.add(source_id)
                    if sources[source_id]["source"] != source or sources[source_id]["consulting"] != record["consulting"]:
                        conflicting_duplicate_ids.add(source_id)
                else:
                    sources[source_id] = record

    labels_by_source: defaultdict[str, list[dict]] = defaultdict(list)
    with ThreadPoolExecutor(max_workers=12) as pool:
        for path, payload in pool.map(_read_json, label_files):
            source_id = str(payload.get("source", {}).get("source_id") or "")
            if source_id:
                labels_by_source[source_id].extend(payload.get("qa_data") or [])

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for source_id in sorted(sources):
            record = sources[source_id]
            record["labels"] = labels_by_source.get(source_id, [])
            record["label_count"] = len(record["labels"])
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(output)

    return {
        "source_files": len(source_files),
        "label_files": len(label_files),
        "merged_records": len(sources),
        "labels": sum(len(items) for items in labels_by_source.values()),
        "unmatched_labels": sum(source_id not in sources for source_id in labels_by_source),
        "sources_without_labels": sum(source_id not in labels_by_source for source_id in sources),
        "duplicate_source_ids": len(duplicate_source_ids),
        "conflicting_duplicate_ids": len(conflicting_duplicate_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge complaint source and label JSON files")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(merge_complaints(args.input_dir, args.output))


if __name__ == "__main__":
    main()
