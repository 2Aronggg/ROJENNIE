from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .build_corpus import _case_records
from .embeddings import BATCH_SIZE, embed_texts
from .retrieval import load_jsonl


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


def _candidates(data_dir: Path, chunks_path: Path) -> list[tuple[str, str]]:
    """(chunk_id, text) pairs for every chunk worth embedding. Glossary is a
    display corpus, never used as decision evidence, so it's skipped."""
    pairs = [(chunk.chunk_id, chunk.text) for chunk in load_jsonl(chunks_path)]
    pairs.extend((record["chunk_id"], str(record["text"])) for record in _case_records(data_dir))
    return pairs


def embed_corpus(data_dir: Path, chunks_path: Path, output: Path, *, resume: bool = True) -> dict[str, int]:
    candidates = _candidates(data_dir, chunks_path)
    done = _existing_ids(output) if resume else set()
    pending = [(chunk_id, text) for chunk_id, text in candidates if chunk_id not in done]

    output.parent.mkdir(parents=True, exist_ok=True)
    embedded = 0
    failed = 0
    with output.open("a" if resume else "w", encoding="utf-8") as handle:
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start : start + BATCH_SIZE]
            vectors = embed_texts([text for _, text in batch], task_type="RETRIEVAL_DOCUMENT")
            for (chunk_id, _), vector in zip(batch, vectors):
                if vector is None:
                    failed += 1
                    continue
                handle.write(json.dumps({"chunk_id": chunk_id, "embedding": [round(v, 6) for v in vector]}) + "\n")
                embedded += 1
            handle.flush()
            print(f"{start + len(batch)}/{len(pending)} processed ({embedded} embedded, {failed} failed)", flush=True)
            time.sleep(0.2)  # stay under rate limits over a run this long

    return {"candidates": len(candidates), "already_done": len(done), "embedded": embedded, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed regulation/product/case chunks for hybrid RAG search")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--chunks", type=Path, default=Path("server/rag/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("server/rag/embeddings.jsonl"))
    parser.add_argument("--no-resume", action="store_true", help="Start over instead of skipping already-embedded chunk_ids")
    args = parser.parse_args()
    print(json.dumps(embed_corpus(args.data_dir, args.chunks, args.output, resume=not args.no_resume), ensure_ascii=False))


if __name__ == "__main__":
    main()
