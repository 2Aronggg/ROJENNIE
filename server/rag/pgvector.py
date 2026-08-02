from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from ..schemas import EvidenceRef
from ..supabase_store import SupabaseStore


LOGGER = logging.getLogger(__name__)


class SupabaseVectorStore:
    """Query the Supabase pgvector RPC without loading the local corpus."""

    def __init__(self, store: SupabaseStore | None = None) -> None:
        self.store = store or SupabaseStore()

    @property
    def enabled(self) -> bool:
        flag = os.getenv("SUPABASE_RAG_ENABLED", "false").strip().lower()
        return flag in {"1", "true", "yes", "on"} and bool(
            self.store.base_url and self.store.api_key
        )

    def search(
        self,
        query_embedding: list[float] | None,
        *,
        product: str | None = None,
        as_of: date | None = None,
        top_k: int = 5,
    ) -> list[EvidenceRef]:
        if not self.enabled or not query_embedding:
            return []

        try:
            rows = self.store.rpc(
                "match_rag_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": min(max(top_k, 1), 50),
                    "filter_product": product or None,
                    "filter_as_of": as_of.isoformat() if as_of else None,
                },
            )
        except Exception as exc:
            LOGGER.warning("Supabase pgvector search failed: %s", exc)
            return []

        results: list[EvidenceRef] = []
        for row in rows:
            try:
                results.append(
                    EvidenceRef(
                        doc_id=str(row["doc_id"]),
                        chunk_id=str(row["chunk_id"]),
                        path=str(row["path"]),
                        page=int(row.get("page") or 1),
                        section=row.get("section"),
                        score=round(float(row.get("similarity") or 0.0), 4),
                        snippet=str(row.get("content") or "")[:280],
                        effective_from=row.get("effective_from"),
                        effective_to=row.get("effective_to"),
                        match_type="vector",
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                LOGGER.warning("Skipping malformed pgvector result: %s", exc)
        return results
