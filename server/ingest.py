from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
from datetime import date
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from zipfile import ZipFile

import olefile
from pypdf import PdfReader

from .schemas import DocumentChunk


PRODUCT_KEYWORDS = (
    ("대출", "product_manual", ["대출"]),
    ("여신", "product_manual", ["대출"]),
    ("예금", "product_manual", ["예금"]),
    ("적금", "product_manual", ["적금"]),
    ("펀드", "product_manual", ["펀드"]),
    ("ELS", "product_manual", ["ELS"]),
    ("ISA", "product_manual", ["예금"]),
)
LAW_KEYWORDS = ("공통규정", "법안", "금융소비자", "은행법", "자본시장")
CASE_KEYWORDS = ("금감원", "판례", "분쟁", "민원")

DATE_RE = re.compile(r"(?<!\d)(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)")
FILENAME_DATE_RE = re.compile(r"(20\d{6})")
EFFECTIVE_RE = re.compile(r"\[?시행\s*(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\]?")
SECTION_RE = re.compile(r"제\s*\d+조(?:의\s*\d+)?(?:\([^\n)]{1,80}\))?")
HWP_TEXT_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9\s.,!?%()ㆍ·\-~\[\]『』「」:;]+")
TABLE_SPLIT_RE = re.compile(r"\t+|\s{2,}")
TABLE_HINT_RE = re.compile(r"(금리|이자|수수료|상환|기간|한도|담보|보증|연체|비율|율|금액|원|%|개월|년)")


def _to_date(year: str, month: str, day: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _date_from_filename(name: str) -> date | None:
    match = FILENAME_DATE_RE.search(name)
    if not match:
        return None
    value = match.group(1)
    return _to_date(value[:4], value[4:6], value[6:8])


def _date_from_text(text: str, pattern: re.Pattern[str] = DATE_RE) -> date | None:
    match = pattern.search(text)
    return _to_date(*match.groups()) if match else None


def _doc_id(relative_path: Path) -> str:
    return hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:12]


def _metadata(file_path: Path, data_dir: Path) -> tuple[str, str, list[str], str, date | None]:
    relative = file_path.relative_to(data_dir)
    haystack = " ".join(relative.parts)
    doc_type = "unknown"
    products = ["미분류"]

    if any(keyword in haystack for keyword in LAW_KEYWORDS):
        doc_type, products = "law", ["공통"]
    if any(keyword in haystack for keyword in CASE_KEYWORDS):
        doc_type, products = "fss_case", _case_products(relative.name)
    for keyword, candidate_doc_type, candidate_products in PRODUCT_KEYWORDS:
        if keyword in haystack:
            doc_type, products = candidate_doc_type, candidate_products
            break
    if "ELS" in haystack.upper():
        doc_type, products = "product_manual", ["ELS"]

    return _doc_id(relative), doc_type, products, f"local:{relative.as_posix()}", _date_from_filename(file_path.name)


def _case_products(name: str) -> list[str]:
    upper_name = name.upper()
    if "ELS" in upper_name:
        return ["ELS"]
    if any(keyword in name for keyword in ("펀드", "투자", "자산", "손실", "ETF")):
        return ["펀드"]
    if any(keyword in name for keyword in ("대출", "여신", "상환", "담보")):
        return ["대출", "공통"]
    if any(keyword in name for keyword in ("예금", "통장", "적금")):
        return ["예금", "공통"]
    return ["공통"]


def _chunks(text: str, max_chars: int = 1400) -> Iterable[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return
    words = text.split(" ")
    current: list[str] = []
    length = 0
    for word in words:
        if current and length + len(word) + 1 > max_chars:
            yield " ".join(current)
            current = []
            length = 0
        current.append(word)
        length += len(word) + 1
    if current:
        yield " ".join(current)


def _table_cells(line: str) -> list[str]:
    cells = [cell.strip(" |") for cell in TABLE_SPLIT_RE.split(line.strip()) if cell.strip(" |")]
    if len(cells) >= 2:
        return cells
    if "|" in line:
        return [cell.strip() for cell in line.strip("| ").split("|") if cell.strip()]
    return []


def _looks_like_table_line(line: str) -> bool:
    cells = _table_cells(line)
    if len(cells) < 2:
        return False
    return len(cells) >= 3 or bool(TABLE_HINT_RE.search(line))


def _table_groups(page_text: str) -> list[list[list[str]]]:
    groups: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw_line in page_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip() if "\t" not in raw_line else raw_line.strip()
        if _looks_like_table_line(line):
            current.append(_table_cells(line))
            continue
        if len(current) >= 2:
            groups.append(current)
        current = []
    if len(current) >= 2:
        groups.append(current)
    return groups


def _markdown_table(rows: list[list[str]]) -> tuple[str, str, list[str]]:
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    body = normalized[1:]
    markdown = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    markdown.extend("| " + " | ".join(row) + " |" for row in body)
    parse_status = "ok"
    risk_flags: list[str] = []
    if len({len(row) for row in rows}) > 1:
        parse_status = "uncertain"
        risk_flags.append("table_parse_uncertain")
    return "\n".join(markdown), parse_status, risk_flags


def _chunks_from_pages(file_path: Path, data_dir: Path, pages: list[str], max_chars: int = 1400) -> list[DocumentChunk]:
    doc_id, doc_type, products, source, published_at = _metadata(file_path, data_dir)
    document_text = "\n".join(pages)
    published_at = published_at or _date_from_text(document_text)

    effective_from = None
    for page_text in pages:
        candidate = _date_from_text(page_text, EFFECTIVE_RE)
        if candidate:
            effective_from = candidate
            break

    chunks: list[DocumentChunk] = []
    for page_number, text in enumerate(pages, start=1):
        section_match = SECTION_RE.search(text)
        section = section_match.group(0) if section_match else f"page:{page_number}"
        for chunk_number, chunk_text in enumerate(_chunks(text, max_chars), start=1):
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}-p{page_number}-c{chunk_number}",
                    path=source,
                    doc_type=doc_type,
                    product=products,
                    source="local",
                    published_at=published_at,
                    effective_from=effective_from,
                    page=page_number,
                    section=section,
                    text=chunk_text,
                    content_type="text",
                    parse_status="ok",
                )
            )
        for table_number, rows in enumerate(_table_groups(text), start=1):
            markdown, parse_status, risk_flags = _markdown_table(rows)
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}-p{page_number}-t{table_number}",
                    path=source,
                    doc_type=doc_type,
                    product=products,
                    source="local",
                    published_at=published_at,
                    effective_from=effective_from,
                    page=page_number,
                    section=f"{section} / table:{table_number}",
                    text=markdown,
                    content_type="table",
                    parse_status=parse_status,
                    risk_flags=risk_flags,
                )
            )
    return chunks


def extract_pdf_chunks(pdf_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return _chunks_from_pages(pdf_path, data_dir, pages, max_chars)


def extract_hwpx_chunks(hwpx_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    pages: list[str] = []
    with ZipFile(hwpx_path) as archive:
        section_names = sorted(name for name in archive.namelist() if name.startswith("Contents/section") and name.endswith(".xml"))
        for name in section_names:
            root = ElementTree.fromstring(archive.read(name))
            texts = [node.text for node in root.iter() if node.text and node.text.strip()]
            pages.append(" ".join(texts))
    return _chunks_from_pages(hwpx_path, data_dir, pages or [""], max_chars)


def extract_hwp_chunks(hwp_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    pages: list[str] = []
    with olefile.OleFileIO(str(hwp_path)) as ole:
        compressed = _hwp_is_compressed(ole)
        section_paths = sorted(path for path in ole.listdir() if len(path) == 2 and path[0] == "BodyText" and path[1].startswith("Section"))
        for path in section_paths:
            payload = ole.openstream(path).read()
            if compressed:
                payload = zlib.decompress(payload, -15)
            pages.append(_decode_hwp_section(payload))
    return _chunks_from_pages(hwp_path, data_dir, pages or [""], max_chars)


def _hwp_is_compressed(ole: olefile.OleFileIO) -> bool:
    if not ole.exists("FileHeader"):
        return False
    header = ole.openstream("FileHeader").read()
    return len(header) > 36 and bool(header[36] & 0x01)


def _decode_hwp_section(payload: bytes) -> str:
    spans: list[str] = []
    offset = 0
    while offset + 4 <= len(payload):
        header = int.from_bytes(payload[offset : offset + 4], "little")
        offset += 4
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > len(payload):
                break
            size = int.from_bytes(payload[offset : offset + 4], "little")
            offset += 4
        record = payload[offset : offset + size]
        offset += size
        if tag_id == 67:
            spans.append(record.decode("utf-16le", errors="ignore"))
    text = " ".join(spans) if spans else payload.decode("utf-16le", errors="ignore")
    return " ".join(HWP_TEXT_RE.findall(text))


def extract_document_chunks(file_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_chunks(file_path, data_dir, max_chars)
    if suffix == ".hwpx":
        return extract_hwpx_chunks(file_path, data_dir, max_chars)
    if suffix == ".hwp":
        return extract_hwp_chunks(file_path, data_dir, max_chars)
    return []


def iter_pdf_chunks(data_dir: Path) -> Iterable[DocumentChunk]:
    for file_path in sorted(path for path in data_dir.rglob("*") if path.suffix.lower() in {".pdf", ".hwp", ".hwpx"}):
        yield from extract_document_chunks(file_path, data_dir)


def write_jsonl(chunks: Iterable[DocumentChunk], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(chunk.model_dump_json() + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract local documents into RAG chunks")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    chunks = list(iter_pdf_chunks(args.data_dir))
    if args.output:
        write_jsonl(chunks, args.output)
    print(json.dumps({"documents": len({chunk.doc_id for chunk in chunks}), "chunks": len(chunks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
