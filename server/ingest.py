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


PDF_DIRS = {
    "공통규정": ("law", ["공통"]),
    "예금 상품 설명서": ("product_manual", ["예금"]),
    "KB은행_상품_data": ("product_manual", ["예금"]),
    "KB_예금_data": ("product_manual", ["예금"]),
    "KB_예금": ("product_manual", ["예금"]),
    "KB_ 적금_data": ("product_manual", ["적금"]),
    "KB_적금": ("product_manual", ["적금"]),
    "KB_펀드_data": ("product_manual", ["펀드"]),
    "KB_펀드": ("product_manual", ["펀드"]),
    "펀드 상품 설명서": ("product_manual", ["펀드"]),
}
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)")
FILENAME_DATE_RE = re.compile(r"(20\d{6})")
EFFECTIVE_RE = re.compile(r"\[시행\s*(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\]")
SECTION_RE = re.compile(r"제\s*\d+조(?:의\d+)?(?:\([^\n)]{1,80}\))?")
HWP_TEXT_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9\s.,!?%()ㆍ·:\-~\[\]「」『』제호]+")


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
    folder = relative.parts[0]
    doc_type, products = PDF_DIRS.get(folder, ("unknown", ["미분류"]))
    if "금감원_판례" in relative.parts:
        doc_type, products = "fss_case", _case_products(relative.name)
    if folder in {"펀드 상품 설명서", "KB_펀드_data", "KB_펀드"} and "ELS" in file_path.name.upper():
        products = ["ELS"]
    return _doc_id(relative), doc_type, products, f"local:{relative.as_posix()}", _date_from_filename(file_path.name)


def _case_products(name: str) -> list[str]:
    upper_name = name.upper()
    if "ELS" in upper_name:
        return ["ELS"]
    if any(keyword in name for keyword in ("금투", "펀드", "투자", "신탁", "ETF")):
        return ["펀드"]
    if any(keyword in name for keyword in ("예금", "통장", "은행")):
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


def _chunks_from_pages(file_path: Path, data_dir: Path, pages: list[str], max_chars: int = 1400) -> list[DocumentChunk]:
    doc_id, doc_type, products, source, published_at = _metadata(file_path, data_dir)
    document_text = "\n".join(pages)

    # 파일명에 날짜가 없으면 본문 날짜를 보조값으로 사용한다.
    published_at = published_at or _date_from_text(document_text)

    # 법령의 시행일은 문서 전체에 적용한다. 종료일은 원문에서 확인하지 못하면 추정하지 않는다.
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
    parser = argparse.ArgumentParser(description="Extract local PDF documents into RAG chunks")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    chunks = list(iter_pdf_chunks(args.data_dir))
    if args.output:
        write_jsonl(chunks, args.output)
    print(json.dumps({"documents": len({chunk.doc_id for chunk in chunks}), "chunks": len(chunks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
