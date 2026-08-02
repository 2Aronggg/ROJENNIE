from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build_corpus import _case_records, _guide_records
from .morphology import extract_stems
from .retrieval import load_jsonl


# regulations는 6만4천+ 청크라 여기서 제외한다 - 형태소 분석은 청크당 ~23ms라
# 전체를 돌리면 25분이 걸리고, 실패 사례는 전부 cases/products 쪽이었다.
# 필요해지면 이 목록에 "regulations"를 추가하면 되지만 그만큼 재계산 비용이 커진다.
STEM_CORPORA = frozenset({"cases", "products", "guides"})


def _existing_ids(output: Path) -> set[str]:
    if not output.exists():
        return set()
    ids: set[str] = set()
    with output.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            ids.add(json.loads(line)["chunk_id"])
    return ids


def _candidates(data_dir: Path, chunks_path: Path) -> list[tuple[str, str, str]]:
    """(chunk_id, text, corpus) triples restricted to STEM_CORPORA."""
    from .build_corpus import _bucket

    pairs: list[tuple[str, str, str]] = []
    for chunk in load_jsonl(chunks_path):
        corpus = _bucket(chunk.path)
        if corpus in STEM_CORPORA:
            pairs.append((chunk.chunk_id, chunk.text, corpus))
    for record in _case_records(data_dir):
        pairs.append((str(record["chunk_id"]), str(record["text"]), "cases"))
    for record in _guide_records(data_dir):
        pairs.append((str(record["chunk_id"]), str(record["text"]), "guides"))

    unique: dict[str, tuple[str, str]] = {}
    for chunk_id, text, corpus in pairs:
        unique.setdefault(chunk_id, (text, corpus))
    return [(chunk_id, text, corpus) for chunk_id, (text, corpus) in unique.items()]


def stem_corpus(data_dir: Path, chunks_path: Path, output: Path, *, resume: bool = True) -> dict[str, int]:
    candidates = _candidates(data_dir, chunks_path)
    done = _existing_ids(output) if resume else set()
    pending = [(chunk_id, text) for chunk_id, text, _ in candidates if chunk_id not in done]

    output.parent.mkdir(parents=True, exist_ok=True)
    processed = 0
    with output.open("a" if resume else "w", encoding="utf-8") as handle:
        for chunk_id, text in pending:
            stems = extract_stems(text)
            handle.write(json.dumps({"chunk_id": chunk_id, "stems": stems}, ensure_ascii=False) + "\n")
            processed += 1
            if processed % 200 == 0:
                handle.flush()
                print(f"{processed}/{len(pending)} processed", flush=True)

    return {"candidates": len(candidates), "already_done": len(done), "processed": processed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute morphological stems for cases/products/guides chunks")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--chunks", type=Path, default=Path("server/rag/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("server/rag/stems.jsonl"))
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(stem_corpus(args.data_dir, args.chunks, args.output, resume=not args.no_resume), ensure_ascii=False))


if __name__ == "__main__":
    main()
