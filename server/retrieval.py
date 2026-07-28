from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .ingest import iter_pdf_chunks
from .schemas import DocumentChunk, EvidenceRef


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


class SearchIndex:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "SearchIndex":
        return cls(list(iter_pdf_chunks(data_dir)))

    def search(
        self,
        query: str,
        *,
        product: str | None = None,
        as_of: date | None = None,
        top_k: int = 5,
    ) -> list[EvidenceRef]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        ranked: list[tuple[float, DocumentChunk]] = []
        for chunk in self.chunks:
            if product and product not in chunk.product and "공통" not in chunk.product:
                continue
            if as_of and chunk.effective_from and chunk.effective_from > as_of:
                continue
            overlap = len(query_tokens & _tokens(chunk.text))
            if not overlap:
                continue
            score = overlap / len(query_tokens)
            if product and product in chunk.product:
                score += 0.25
            ranked.append((score, chunk))

        ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
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
            )
            for score, chunk in ranked[:top_k]
        ]
