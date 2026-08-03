"""Vercel entry point.

Vercel's Python runtime looks for an ASGI/WSGI callable named `app` in files
under api/. The FastAPI instance itself lives in server/app.py; this module
only makes it importable from the repository root, which is where Vercel runs
the function from.

Two things must hold for this to serve real answers in production:

- data/corpus/all.jsonl has to be in the deployment. It is the only corpus
  file the server reads (server/app.py CHUNKS_PATH), and .gitignore keeps an
  explicit exception for it.
- MOCK_BANK_DB=:memory: has to be set. Serverless filesystems are read-only,
  and MockBankClient writes its seed data on construction. It falls back to
  memory on its own if the write fails, but setting it avoids the failed
  attempt on every cold start.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.app import app  # noqa: E402

__all__ = ["app"]
