from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .ingest import _chunks, iter_document_chunks
from .retrieval import load_jsonl
from ..schemas import DocumentChunk


CSV_FIELD_LIMIT = 1024 * 1024 * 1024


def _id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _bucket(path: str) -> str | None:
    relative = path.split(":", 1)[-1].replace("\\", "/")
    if relative.startswith(("regulations/", "공통규정/")):
        return "regulations"
    if relative.startswith("products/"):
        return "products"
    if relative.startswith("cases/"):
        return "cases"
    return None


def _record(chunk: DocumentChunk, corpus: str, **extra: object) -> dict[str, object]:
    record = chunk.model_dump(mode="json")
    record.update({"corpus": corpus, "parent_id": chunk.doc_id, **extra})
    return record


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    csv.field_size_limit(CSV_FIELD_LIMIT)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def _case_records(data_dir: Path) -> list[dict[str, object]]:
    path = data_dir / "cases" / "cases.csv"
    if not path.exists():
        return []
    _, rows = _read_csv(path)
    records: list[dict[str, object]] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text or row.get("status") not in {"", "ok", None}:
            continue
        source_file = row.get("source_file") or "case"
        doc_id = _id(f"cases/{source_file}")
        product = (row.get("product") or "공통").strip() or "공통"
        for number, text_chunk in enumerate(_chunks(text), start=1):
            chunk = DocumentChunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}-c{number}",
                path=f"local:cases/{source_file}",
                doc_type="case",
                product=[product],
                source="local",
                page=1,
                section=row.get("title") or None,
                text=text_chunk,
            )
            records.append(_record(chunk, "cases", source_file=source_file, format=row.get("format", "")))
    return records


def _glossary_records(data_dir: Path) -> list[dict[str, object]]:
    path = data_dir / "dictionary" / "fine_financial_glossary.csv"
    if not path.exists():
        return []
    _, rows = _read_csv(path)
    doc_id = _id("dictionary/fine_financial_glossary.csv")
    records: list[dict[str, object]] = []
    for number, row in enumerate(rows, start=1):
        term = (row.get("term") or "").strip()
        definition = (row.get("definition") or "").strip()
        if not term or not definition:
            continue
        chunk = DocumentChunk(
            doc_id=doc_id,
            chunk_id=f"{doc_id}-c{number}",
            path="local:dictionary/fine_financial_glossary.csv",
            doc_type="glossary",
            product=["공통"],
            source="local",
            page=1,
            section=term,
            text=f"{term}: {definition}",
        )
        records.append(_record(chunk, "glossary", term=term, source_url=row.get("source_url", "")))
    return records


def build_corpus(data_dir: Path, chunks_path: Path, output_dir: Path) -> dict[str, object]:
    chunks = load_jsonl(chunks_path) if chunks_path.exists() else list(iter_document_chunks(data_dir))
    grouped: dict[str, list[dict[str, object]]] = {
        "regulations": [],
        "products": [],
        "cases": [],
        "glossary": [],
    }
    for chunk in chunks:
        corpus = _bucket(chunk.path)
        if corpus in grouped:
            grouped[corpus].append(_record(chunk, corpus))
    grouped["cases"].extend(_case_records(data_dir))
    grouped["glossary"].extend(_glossary_records(data_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    all_records: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    documents: dict[str, int] = {}
    for corpus, records in grouped.items():
        _write_jsonl(output_dir / f"{corpus}.jsonl", records)
        all_records.extend(records)
        counts[corpus] = len(records)
        documents[corpus] = len({record["doc_id"] for record in records})
    _write_jsonl(output_dir / "all.jsonl", all_records)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embedding_status": "not_generated",
        "retrieval": "full_text_with_optional_vector_score",
        "corpora": counts,
        "documents": documents,
        "total_chunks": len(all_records),
        "authoritative_for_decision": ["regulations", "products", "cases"],
        "display_only": ["glossary"],
        "excluded": ["complaints"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build purpose-specific RAG corpora")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--chunks", type=Path, default=Path("server/rag/chunks.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/corpus"))
    args = parser.parse_args()
    print(json.dumps(build_corpus(args.data_dir, args.chunks, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
