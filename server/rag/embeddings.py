from __future__ import annotations

import logging
import time
from typing import Any

from ..policy.gateway import redact_pii


LOGGER = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
# Matryoshka-truncated: the default 3072-dim vector would put ~8GB of Python
# float lists in memory across the full corpus. 768 keeps retrieval quality
# while staying survivable to load and search over.
OUTPUT_DIMENSIONALITY = 768
BATCH_SIZE = 100
MAX_RETRIES = 3


def _client() -> Any:
    from server.agents.router import _gemini_client

    return _gemini_client()


def embed_texts(
    texts: list[str],
    *,
    task_type: str,
    client: Any | None = None,
) -> list[list[float] | None]:
    """Embed a batch of texts. Failures degrade to None per-text, never raise -
    embeddings are a search-ranking enhancement, not something a request should
    fail over, matching how every other LLM call in this codebase falls back."""
    if not texts:
        return []
    active_client = client or _client()
    from google.genai import errors, types

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = active_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=OUTPUT_DIMENSIONALITY,
                ),
            )
            return [list(item.values) if item.values else None for item in response.embeddings]
        except errors.APIError as exc:
            LOGGER.warning("embedding attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
        except Exception as exc:  # keep one bad batch from failing the whole run
            LOGGER.warning("embedding batch failed: %s", exc)
            break
    return [None] * len(texts)


def embed_query(text: str, *, client: Any | None = None) -> list[float] | None:
    """Embed a single user-derived query. Direct identifiers are masked first,
    same as every other text this codebase sends to Gemini."""
    safe_text, _ = redact_pii(text)
    if not safe_text.strip():
        return None
    results = embed_texts([safe_text], task_type="RETRIEVAL_QUERY", client=client)
    return results[0] if results else None
