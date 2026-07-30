from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from .schemas import DocumentChunk


PDF_DIRS = {
    "regulations": ("law", ["공통"]),
    "products/deposit": ("product_manual", ["예금", "적금"]),
    "products/fund": ("product_manual", ["펀드"]),
    "cases": ("case", ["공통"]),
    "complaints": ("complaint", ["공통"]),
    "공통규정": ("law", ["공통"]),
    "예금 상품 설명서": ("product_manual", ["예금", "적금"]),
    "펀드 상품 설명서": ("product_manual", ["펀드"]),
}
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)")
FILENAME_DATE_RE = re.compile(r"(20\d{6})")
EFFECTIVE_RE = re.compile(r"\[시행\s*(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\]")
SECTION_RE = re.compile(r"제\s*\d+조(?:의\d+)?(?:\([^\n)]{1,80}\))?")


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


def _metadata(pdf_path: Path, data_dir: Path) -> tuple[str, str, list[str], str, date | None]:
    relative = pdf_path.relative_to(data_dir)
    folder = relative.parts[0]
    category = "/".join(relative.parts[:2]) if folder == "products" and len(relative.parts) > 1 else folder
    doc_type, products = PDF_DIRS.get(category, ("unknown", ["미분류"]))
    if category in {"products/fund", "펀드 상품 설명서"} and "ELS" in pdf_path.name.upper():
        products = ["ELS"]
    return _doc_id(relative), doc_type, products, f"local:{relative.as_posix()}", _date_from_filename(pdf_path.name)


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


def extract_pdf_chunks(pdf_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    doc_id, doc_type, products, source, published_at = _metadata(pdf_path, data_dir)
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _api_date(value: Any) -> date | None:
    raw = str(value or "")
    if re.fullmatch(r"20\d{6}", raw):
        return _to_date(raw[:4], raw[4:6], raw[6:8])
    return _date_from_text(raw)


def _api_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [text for item in value for text in _api_text(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _api_text(item)]
    text = str(value).strip()
    return [text] if text else []


def _article_text(article: dict[str, Any]) -> str:
    parts = _api_text(article.get("조문내용"))
    for paragraph in _as_list(article.get("항")):
        if not isinstance(paragraph, dict):
            continue
        parts.extend(_api_text(paragraph.get("항내용")))
        for item in _as_list(paragraph.get("호")):
            if isinstance(item, dict):
                parts.extend(_api_text(item.get("호내용")))
    return "\n".join(parts)


def _api_document_chunks(api_path: Path, data_dir: Path, max_chars: int = 1400) -> list[DocumentChunk]:
    payload = json.loads(api_path.read_text(encoding="utf-8"))
    law = payload.get("법령", {})
    basic = law.get("기본정보", {})
    relative = api_path.relative_to(data_dir)
    doc_id = _doc_id(relative)
    source = f"api:{relative.as_posix()}"
    published_at = _api_date(basic.get("공포일자"))
    effective_from = _api_date(basic.get("시행일자"))
    product = ["공통"]
    chunks: list[DocumentChunk] = []
    sequence = 0

    def add(text: str, section: str, effective: date | None = effective_from) -> None:
        nonlocal sequence
        for text_chunk in _chunks(text, max_chars):
            sequence += 1
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}-c{sequence}",
                    path=source,
                    doc_type="law",
                    product=product,
                    source="local",
                    published_at=published_at,
                    effective_from=effective,
                    page=1,
                    section=section,
                    text=text_chunk,
                )
            )

    article_units = _as_list((law.get("조문") or {}).get("조문단위"))
    for article in article_units:
        if not isinstance(article, dict):
            continue
        text = _article_text(article)
        if text:
            add(text, article.get("조문제목") or article.get("조문내용") or "조문", _api_date(article.get("조문시행일자")) or effective_from)

    appendix_units = _as_list((law.get("부칙") or {}).get("부칙단위"))
    promulgation_number = str(basic.get("공포번호") or "")
    for appendix in appendix_units:
        if not isinstance(appendix, dict):
            continue
        if promulgation_number and str(appendix.get("부칙공포번호") or "") != promulgation_number:
            continue
        text = "\n".join(_api_text(appendix.get("부칙내용")))
        if text:
            add(text, "부칙")

    for key, section in (("개정문", "개정문"), ("제개정이유", "제개정이유")):
        text = "\n".join(_api_text((law.get(key) or {}).get(f"{key}내용")))
        if text:
            add(text, section)
    return chunks


def iter_pdf_chunks(data_dir: Path) -> Iterable[DocumentChunk]:
    for pdf_path in sorted(data_dir.rglob("*.pdf")):
        yield from extract_pdf_chunks(pdf_path, data_dir)


def iter_document_chunks(data_dir: Path) -> Iterable[DocumentChunk]:
    yield from iter_pdf_chunks(data_dir)
    api_dir = data_dir / "regulations" / "law_api"
    for api_path in sorted(api_dir.glob("*.json")):
        if api_path.name == "manifest.json":
            continue
        yield from _api_document_chunks(api_path, data_dir)


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
    chunks = list(iter_document_chunks(args.data_dir))
    if args.output:
        write_jsonl(chunks, args.output)
    print(json.dumps({"documents": len({chunk.doc_id for chunk in chunks}), "chunks": len(chunks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
