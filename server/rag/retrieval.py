from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from .ingest import iter_document_chunks, write_jsonl
from ..schemas import DocumentChunk, EvidenceRef


TOKEN_RE = re.compile(r"[\uac00-\ud7a3A-Za-z0-9]+")
COMMON_PRODUCT = "\uacf5\ud1b5"
RRF_K = 60


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _corpus_for(chunk: DocumentChunk) -> str:
    path = chunk.path.split(":", 1)[-1].replace("\\", "/")
    if chunk.doc_type == "glossary" or path.startswith("dictionary/"):
        return "glossary"
    if chunk.doc_type == "case" or path.startswith("cases/"):
        return "cases"
    if chunk.doc_type == "law" or path.startswith(("regulations/", "공통규정/")):
        return "regulations"
    if path.startswith("products/"):
        return "products"
    return "other"


def load_jsonl(path: Path) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    if not path.exists():
        return chunks
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                chunks.append(DocumentChunk.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                continue
    return chunks


def document_manifest(data_dir: Path) -> dict[str, dict[str, int]]:
    manifest: dict[str, dict[str, int]] = {}
    paths = list(data_dir.rglob("*.pdf"))
    paths.extend((data_dir / "regulations" / "law_api").glob("*.json"))
    for path in sorted(paths):
        if path.name == "manifest.json":
            continue
        stat = path.stat()
        manifest[path.relative_to(data_dir).as_posix()] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    return manifest


def changed_documents(
    current: dict[str, dict[str, int]],
    previous: dict[str, dict[str, int]],
) -> list[str]:
    return sorted(
        path
        for path in set(current) | set(previous)
        if current.get(path) != previous.get(path)
    )


def needs_reindex(data_dir: Path, chunks_path: Path) -> bool:
    if not chunks_path.exists():
        return True
    artifact_mtime = chunks_path.stat().st_mtime_ns
    sources = (
        list(data_dir.rglob("*.pdf"))
        + list((data_dir / "regulations" / "law_api").glob("*.json"))
        + [
            path
            for path in (
                data_dir / "cases" / "cases.csv",
                data_dir / "dictionary" / "fine_financial_glossary.csv",
            )
            if path.exists()
        ]
    )
    return any(
        path.stat().st_mtime_ns > artifact_mtime
        for path in sources
        if path.name != "manifest.json"
    )


def reindex(data_dir: Path, output: Path) -> int:
    return write_jsonl(iter_document_chunks(data_dir), output)


class SearchIndex:
    def __init__(self, chunks: list[DocumentChunk], *, source: str = "memory"):
        self.chunks = chunks
        self.source = source
        self._token_sets: list[set[str]] = []
        self._token_index: dict[str, set[int]] = defaultdict(set)
        self._document_frequency: Counter[str] = Counter()
        for index, chunk in enumerate(chunks):
            tokens = _tokens(chunk.text)
            self._token_sets.append(tokens)
            for token in tokens:
                self._token_index[token].add(index)
                self._document_frequency[token] += 1

    @classmethod
    def from_jsonl(cls, path: Path) -> "SearchIndex":
        return cls(load_jsonl(path), source=f"jsonl:{path}")

    @classmethod
    def from_data_dir(
        cls,
        data_dir: Path,
        *,
        chunks_path: Path | None = None,
    ) -> "SearchIndex":
        if chunks_path and chunks_path.exists() and not needs_reindex(data_dir, chunks_path):
            index = cls.from_jsonl(chunks_path)
            if index.chunks:
                return index
        return cls(list(iter_document_chunks(data_dir)), source=f"data:{data_dir}")

    def search(
        self,
        query: str,
        *,
        product: str | None = None,
        as_of: date | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[EvidenceRef]:
        query_tokens = _tokens(query)
        if not query_tokens and not query_embedding:
            return []

        if query_tokens:
            candidate_indices = set().union(
                *(self._token_index.get(token, set()) for token in query_tokens)
            )
        else:
            candidate_indices = set(range(len(self.chunks)))

        query_idf = {
            token: math.log1p(
                (len(self.chunks) - self._document_frequency.get(token, 0) + 0.5)
                / (self._document_frequency.get(token, 0) + 0.5)
            )
            for token in query_tokens
        }
        idf_total = sum(query_idf.values()) or 1.0
        ranked: list[tuple[float, str, DocumentChunk, str]] = []
        for index in candidate_indices:
            chunk = self.chunks[index]
            # Glossary is a display corpus, not a legal or contractual decision source.
            if _corpus_for(chunk) == "glossary":
                continue
            if product and product not in chunk.product and COMMON_PRODUCT not in chunk.product:
                continue
            if as_of and chunk.effective_from and chunk.effective_from > as_of:
                continue
            if as_of and chunk.effective_to and chunk.effective_to < as_of:
                continue

            tokens = self._token_sets[index]
            weighted_overlap = sum(query_idf[token] for token in query_tokens if token in tokens)
            text_score = weighted_overlap / idf_total if query_tokens else 0.0
            vector_score = 0.0
            if query_embedding and chunk.embedding:
                vector_score = max(0.0, _cosine(query_embedding, chunk.embedding))
            if not text_score and not vector_score:
                continue

            if text_score and vector_score:
                score = 0.7 * text_score + 0.3 * vector_score
                match_type = "hybrid"
            elif vector_score:
                score = vector_score
                match_type = "vector"
            else:
                score = text_score
                match_type = "full_text"
            if product and product in chunk.product:
                score += 0.18
            elif product and COMMON_PRODUCT in chunk.product:
                score += 0.04
            ranked.append((score, chunk.chunk_id, chunk, match_type))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            EvidenceRef(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                path=chunk.path,
                page=chunk.page,
                section=chunk.section,
                score=round(score, 4),
                snippet=chunk.text[:280],
                effective_from=chunk.effective_from,
                effective_to=chunk.effective_to,
                match_type=match_type,
            )
            for score, _, chunk, match_type in ranked[:top_k]
        ]

    def search_many(
        self,
        queries: Sequence[str],
        *,
        product: str | None = None,
        as_of: date | None = None,
        top_k: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[EvidenceRef]:
        """Fuse focused retrieval queries with reciprocal rank fusion."""
        unique_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
        if not unique_queries:
            return []
        candidates: dict[str, tuple[EvidenceRef, float]] = {}
        per_query_limit = max(top_k * 4, 20)
        for query in unique_queries:
            for rank, evidence in enumerate(
                self.search(
                    query,
                    product=product,
                    as_of=as_of,
                    top_k=per_query_limit,
                    query_embedding=query_embedding,
                ),
                start=1,
            ):
                rrf = 1.0 / (RRF_K + rank)
                previous = candidates.get(evidence.chunk_id)
                if previous is None:
                    candidates[evidence.chunk_id] = (evidence, rrf)
                else:
                    best = previous[0] if previous[0].score >= evidence.score else evidence
                    candidates[evidence.chunk_id] = (best, previous[1] + rrf)

        if not candidates:
            return []
        max_rrf = max(value[1] for value in candidates.values())
        fused: list[tuple[float, EvidenceRef]] = []
        for evidence, rrf in candidates.values():
            score = 0.7 * evidence.score + 0.3 * (rrf / max_rrf)
            fused.append((score, evidence))
        fused.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [
            evidence.model_copy(update={"score": round(score, 4)})
            for score, evidence in fused[:top_k]
        ]

    def date_notices(self, as_of: date) -> list[str]:
        notices: set[str] = set()
        for chunk in self.chunks:
            if chunk.effective_from and chunk.effective_from > as_of:
                notices.add(f"future_effective:{chunk.doc_id}:{chunk.effective_from.isoformat()}")
            if chunk.effective_to and chunk.effective_to < as_of:
                notices.add(f"expired:{chunk.doc_id}:{chunk.effective_to.isoformat()}")
        return sorted(notices)
