from __future__ import annotations

import argparse
import json
from html import unescape
from html.parser import HTMLParser
import math
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://www.kca.go.kr"
LIST_URL = f"{BASE_URL}/odr/api/cm/in/exmplBjItem.do"
DETAIL_URL = f"{BASE_URL}/odr/cm/cm/boardsDtl.do"
BOARD_ID = "00000007"
FINANCE_CATEGORY = "128"
PAGE_SIZE = 10
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _clean(value: str) -> str:
    value = unescape(value).replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self._seq: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        onclick = values.get("onclick") or ""
        match = re.search(r"fn_view_bbd\(\s*[\"'](\d+)[\"']\s*,\s*[\"']00000007[\"']\s*\)", onclick)
        if match:
            self._seq = match.group(1)
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._seq:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._seq:
            self.items.append({"case_id": self._seq, "title": _clean("".join(self._buffer))})
            self._seq = None
            self._buffer = []


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.fields: dict[str, str] = {}
        self._in_title = False
        self._in_content = False
        self._capture_title = False
        self._capture_label = False
        self._capture_value = False
        self._label = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "div" and "board_v_tit" in classes:
            self._in_title = True
        elif tag == "div" and "board_v_con" in classes:
            self._in_content = True
        elif tag == "h4" and self._in_title:
            self._capture_title = True
            self._buffer = []
        elif tag == "th" and self._in_content:
            self._capture_label = True
            self._buffer = []
        elif tag == "span" and self._in_content and self._label:
            self._capture_value = True
            self._buffer = []
        elif tag == "br" and self._capture_value:
            self._buffer.append("\n")

    def handle_data(self, data: str) -> None:
        if self._capture_title or self._capture_label or self._capture_value:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h4" and self._capture_title:
            self.title = _clean("".join(self._buffer))
            self._capture_title = False
        elif tag == "th" and self._capture_label:
            self._label = _clean("".join(self._buffer))
            self._capture_label = False
        elif tag == "span" and self._capture_value:
            value = _clean("".join(self._buffer))
            if value:
                self.fields[self._label] = _clean(f"{self.fields.get(self._label, '')}\n{value}")
            self._capture_value = False
        elif tag == "div" and self._in_content:
            # The parser only needs the fields inside board_v_con; nested divs
            # do not change this flag because the final closing div ends it.
            pass
        elif tag == "div" and self._in_title:
            self._in_title = False


def _post_form(url: str, data: dict[str, str], retries: int = 3) -> str:
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "KB-Key-Buddy-case-research/1.0",
        },
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == retries - 1:
                raise
        except URLError:
            if attempt == retries - 1:
                raise
        time.sleep(2**attempt)
    raise RuntimeError("KCA request failed")


def _list_page(page: int, search_keyword: str = "") -> tuple[int, list[dict[str, str]]]:
    html = _post_form(
        LIST_URL,
        {
            "brdId": BOARD_ID,
            "dataStts": "Y",
            "seq": "",
            "multiItmSeq": FINANCE_CATEGORY,
            "searchCondition": "0",
            "searchKeyword": search_keyword,
            "pageIndex": str(page),
            "pageSize": str(PAGE_SIZE),
        },
    )
    parser = _ListParser()
    parser.feed(html)
    total_match = re.search(r"총\s*<em[^>]*>\s*(\d+)\s*</em>", html)
    return int(total_match.group(1)) if total_match else 0, parser.items


def _product(title: str, text: str) -> str | None:
    if "대출" in title:
        return "대출"
    if "적금" in title:
        return "적금"
    if "예금" in title or "통장" in title or "계좌" in title:
        return "예금"
    if any(keyword in title for keyword in ("ELS", "펀드", "투자", "주식")):
        return "펀드"
    if "대출" in text:
        return "대출"
    if "적금" in text:
        return "적금"
    if "예금" in text:
        return "예금"
    if any(keyword in text for keyword in ("ELS", "펀드", "투자", "주식")):
        return "펀드"
    return None


def _detail(case: dict[str, str]) -> dict[str, str]:
    html = _post_form(
        DETAIL_URL,
        {
            "brdId": BOARD_ID,
            "dataStts": "Y",
            "seq": case["case_id"],
            "multiItmSeq": FINANCE_CATEGORY,
            "searchCondition": "0",
            "searchKeyword": "",
            "pageIndex": "1",
            "pageSize": str(PAGE_SIZE),
        },
    )
    parser = _DetailParser()
    parser.feed(html)
    title = parser.title or case["title"]
    ordered = ("사건개요", "당사자주장", "판단", "결정사항", "관련법률")
    sections = [f"[{label}]\n{parser.fields[label]}" for label in ordered if parser.fields.get(label)]
    text = "\n\n".join(sections)
    product = _product(title, text)
    if not product:
        raise ValueError("unsupported product after detail extraction")
    return {
        "source_file": f"kca_{case['case_id']}.html",
        "format": "html",
        "title": title,
        "product": product,
        "text": text,
        "status": "ok" if text else "empty",
        "error": "",
        "source_url": f"{DETAIL_URL}?seq={case['case_id']}&brdId={BOARD_ID}",
        "source": "kca",
        "authority_level": "secondary",
        "institution": "한국소비자원",
        "category": "금융/보험",
        "case_id": case["case_id"],
        "collected_at": time.strftime("%Y-%m-%d"),
    }


def crawl(output: Path, *, limit: int = 0, delay: float = 0.5, max_pages: int = 0) -> dict[str, int]:
    total, first_page = _list_page(1)
    total_pages = math.ceil(total / PAGE_SIZE)
    pages = min(total_pages, max_pages) if max_pages else total_pages
    listed = list(first_page)
    for page in range(2, int(pages) + 1):
        time.sleep(delay)
        _, items = _list_page(page)
        listed.extend(items)

    unique: dict[str, dict[str, str]] = {item["case_id"]: item for item in listed}
    candidates = list(unique.values())
    if limit:
        candidates = candidates[:limit]

    rows: list[dict[str, str]] = []
    for index, item in enumerate(candidates):
        if limit and len(rows) >= limit:
            break
        if index:
            time.sleep(delay)
        try:
            rows.append(_detail(item))
        except ValueError as exc:
            if str(exc) == "unsupported product after detail extraction":
                continue
            raise
        except Exception as exc:
            rows.append(
                {
                    "source_file": f"kca_{item['case_id']}.html",
                    "format": "html",
                    "title": item["title"],
                    "product": _product(item["title"], "") or "공통",
                    "text": "",
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "source_url": f"{DETAIL_URL}?seq={item['case_id']}&brdId={BOARD_ID}",
                    "source": "kca",
                    "authority_level": "secondary",
                    "institution": "한국소비자원",
                    "category": "금융/보험",
                    "case_id": item["case_id"],
                    "collected_at": time.strftime("%Y-%m-%d"),
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"listed": len(unique), "candidates": len(candidates), "written": len(rows), "ok": sum(row["status"] == "ok" for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl KCA financial/insurance dispute decision cases")
    parser.add_argument("--output", type=Path, default=Path("data/cases/kca_cases.jsonl"))
    parser.add_argument("--limit", type=int, default=0, help="0 means all supported-product cases")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--max-pages", type=int, default=0)
    args = parser.parse_args()
    print(crawl(args.output, limit=args.limit, delay=max(args.delay, 0.2), max_pages=args.max_pages))


if __name__ == "__main__":
    main()
