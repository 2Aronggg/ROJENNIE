from __future__ import annotations

import argparse
import csv
import re
import struct
import zlib
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

import olefile


PARA_TEXT = 0x43
PRODUCT_RE = re.compile(r"^\(([^)]+)\)")


def _clean_text(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value).strip()


def _product_from_name(name: str) -> str:
    match = PRODUCT_RE.match(name)
    if match:
        return match.group(1)
    if "대출" in name:
        return "대출"
    return ""


def _decompress_body(data: bytes) -> bytes:
    try:
        return zlib.decompress(data, -15)
    except zlib.error:
        return data


def _hwp_text(path: Path) -> str:
    with olefile.OleFileIO(str(path)) as document:
        if document.exists("PrvText"):
            preview = document.openstream(["PrvText"]).read().decode("utf-16le", errors="ignore")
            if preview.strip():
                return re.sub(r"\n{3,}", "\n\n", preview.replace("\r", "\n")).strip()
        sections = [
            stream
            for stream in document.listdir()
            if len(stream) == 2 and stream[0] == "BodyText"
        ]
        lines: list[str] = []
        for stream in sorted(sections):
            data = _decompress_body(document.openstream(stream).read())
            offset = 0
            while offset + 4 <= len(data):
                header = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                tag = header & 0x3FF
                size = (header >> 20) & 0xFFF
                if size == 0xFFF:
                    if offset + 4 > len(data):
                        break
                    size = struct.unpack_from("<I", data, offset)[0]
                    offset += 4
                payload = data[offset : offset + size]
                offset += size
                if tag != PARA_TEXT:
                    continue
                text = payload.decode("utf-16le", errors="ignore")
                text = "".join(char for char in text if char in "\t\n\r" or ord(char) >= 0x20)
                if text.strip():
                    lines.append(_clean_text(text))
        return "\n".join(lines)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _hwpx_text(path: Path) -> str:
    lines: list[str] = []
    with ZipFile(path) as document:
        names = sorted(
            name
            for name in document.namelist()
            if name.startswith("Contents/section") and name.endswith(".xml")
        )
        for name in names:
            root = ElementTree.fromstring(document.read(name))
            for paragraph in root.iter():
                if _local_name(paragraph.tag) not in {"p", "para"}:
                    continue
                text = "".join(
                    node.text or ""
                    for node in paragraph.iter()
                    if _local_name(node.tag) in {"t", "text"}
                )
                if text.strip():
                    lines.append(_clean_text(text))
    return "\n".join(lines)


def extract_text(path: Path) -> str:
    return _hwpx_text(path) if path.suffix.lower() == ".hwpx" else _hwp_text(path)


def write_cases(input_dir: Path, output: Path) -> int:
    rows: list[dict[str, str]] = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in {".hwp", ".hwpx"}:
            continue
        row = {
            "source_file": path.name,
            "format": path.suffix.lower().lstrip("."),
            "title": path.stem,
            "product": _product_from_name(path.name),
            "text": "",
            "status": "ok",
            "error": "",
        }
        try:
            row["text"] = extract_text(path)
            if not row["text"]:
                row["status"] = "empty"
        except Exception as exc:  # keep one bad source from losing all cases
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["source_file"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract HWP/HWPX case documents into CSV")
    parser.add_argument("--input-dir", type=Path, default=Path("data/cases"))
    parser.add_argument("--output", type=Path, default=Path("data/cases/cases.csv"))
    args = parser.parse_args()
    print({"documents": write_cases(args.input_dir, args.output), "output": str(args.output)})


if __name__ == "__main__":
    main()
