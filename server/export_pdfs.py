from __future__ import annotations

import argparse
import csv
from pathlib import Path

from pypdf import PdfReader


def export_pdfs(data_dir: Path, output: Path) -> int:
    rows: list[dict[str, str | int]] = []
    for path in sorted(data_dir.rglob("*.pdf")):
        relative = path.relative_to(data_dir).as_posix()
        row: dict[str, str | int] = {
            "path": relative,
            "source_file": path.name,
            "category": "/".join(path.relative_to(data_dir).parts[:-1]),
            "page_count": 0,
            "text": "",
            "status": "ok",
            "error": "",
        }
        try:
            reader = PdfReader(str(path))
            row["page_count"] = len(reader.pages)
            row["text"] = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            if not row["text"]:
                row["status"] = "empty"
        except Exception as exc:  # keep one unreadable PDF in the report
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["path"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export every local PDF to one CSV")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/pdf_documents.csv"))
    args = parser.parse_args()
    print({"documents": export_pdfs(args.data_dir, args.output), "output": str(args.output)})


if __name__ == "__main__":
    main()
