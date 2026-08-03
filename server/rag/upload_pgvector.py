from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

from ..agents.router import _load_dotenv
from ..supabase_store import SupabaseStore


MAX_RETRIES = 5
REQUEST_TIMEOUT = 60


def _row(record: dict[str, object]) -> dict[str, object] | None:
    embedding = record.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        return None
    if record.get("doc_type") == "glossary":
        return None
    return {
        "chunk_id": record["chunk_id"],
        "doc_id": record["doc_id"],
        "path": record["path"],
        "doc_type": record["doc_type"],
        "product": record.get("product") or [],
        "issue_types": record.get("issue_types") or [],
        "source": record.get("source") or "local",
        "published_at": record.get("published_at"),
        "effective_from": record.get("effective_from"),
        "effective_to": record.get("effective_to"),
        "page": record.get("page") or 1,
        "section": record.get("section"),
        "content": record.get("text") or "",
        "embedding": embedding,
        "metadata": {
            "corpus": record.get("corpus"),
            "parent_id": record.get("parent_id"),
            "source_file": record.get("source_file"),
            "source_url": record.get("source_url"),
            "institution": record.get("institution"),
            "authority_level": record.get("authority_level"),
        },
    }


def upload(
    input_path: Path,
    batch_size: int,
    limit: int = 0,
    start_line: int = 1,
) -> dict[str, int]:
    store = SupabaseStore()
    if not store.base_url or not store.api_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    batch: list[dict[str, object]] = []
    scanned = uploaded = skipped = 0

    def flush() -> None:
        nonlocal uploaded
        if not batch:
            return
        # on_conflict=chunk_id + merge-duplicates makes a batch safe to retry or
        # re-run wholesale: a row that already made it through is just overwritten
        # with the same values, never duplicated.
        for attempt in range(MAX_RETRIES):
            try:
                store._request(
                    "rag_chunks",
                    method="POST",
                    params={"on_conflict": "chunk_id"},
                    body=batch,
                    prefer="resolution=merge-duplicates,return=minimal",
                    timeout=REQUEST_TIMEOUT,
                )
                break
            except RuntimeError as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = 2**attempt
                print(f"batch failed ({exc}); retrying in {wait}s", file=sys.stderr, flush=True)
                time.sleep(wait)
        uploaded += len(batch)
        batch.clear()
        print(f"uploaded={uploaded}", flush=True)

    with input_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line_number < max(start_line, 1):
                continue
            if limit and scanned >= limit:
                break
            if not line.strip():
                continue
            scanned += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                skipped += 1
                print(
                    f"skipped malformed JSON line {line_number}: {exc}",
                    file=sys.stderr,
                )
                continue
            row = _row(record)
            if row is None:
                skipped += 1
                continue
            batch.append(row)
            if len(batch) >= batch_size:
                flush()
    flush()
    return {"scanned": scanned, "uploaded": uploaded, "skipped": skipped}


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Upload embedded RAG chunks to Supabase pgvector")
    parser.add_argument("--input", type=Path, default=Path("data/corpus/all.jsonl"))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int, default=0, help="0 means all rows")
    parser.add_argument("--start-line", type=int, default=1, help="1-based source line to resume from")
    args = parser.parse_args()
    print(json.dumps(
        upload(args.input, max(args.batch_size, 1), args.limit, args.start_line),
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
