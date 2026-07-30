"""Fetch selected Korean statutes from the Law Open Data API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "regulations" / "law_api"
LAW_NAMES = [
    "금융소비자 보호에 관한 법률",
    "금융소비자 보호에 관한 법률 시행령",
    "은행법",
    "은행법 시행령",
    "자본시장과 금융투자업에 관한 법률",
    "개인금융채권의 관리 및 개인금융채무자의 보호에 관한 법률",
    "개인금융채권의 관리 및 개인금융채무자의 보호에 관한 법률 시행령",
]


def _api_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("LAW_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return os.environ["LAW_API_KEY"]


def _get(target: str, **params: str) -> dict:
    query = urlencode({"OC": _api_key(), "target": target, "type": "JSON", **params})
    request = Request(f"https://www.law.go.kr/DRF/lawSearch.do?{query}")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _items(payload: dict) -> list[dict]:
    value = payload.get("LawSearch", {}).get("law", [])
    return value if isinstance(value, list) else [value] if value else []


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in LAW_NAMES:
        results = [item for item in _items(_get("eflaw", nw="1,3", query=name, display="100")) if item.get("법령명한글") == name]
        for item in results:
            detail_query = urlencode({"OC": _api_key(), "target": "eflaw", "MST": item["법령일련번호"], "type": "JSON", "efYd": item.get("시행일자", "")})
            request = Request(f"https://www.law.go.kr/DRF/lawService.do?{detail_query}")
            with urlopen(request, timeout=30) as response:
                detail = json.loads(response.read().decode("utf-8"))
            safe_name = f"{name}_{item.get('시행일자', 'unknown')}_{item.get('법령일련번호')}.json"
            path = DATA_DIR / safe_name
            path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest.append({
                "name": name,
                "mst": item.get("법령일련번호"),
                "promulgated_at": item.get("공포일자"),
                "effective_from": item.get("시행일자"),
                "revision_type": item.get("제개정구분명"),
                "history": item.get("현행연혁코드"),
                "file": path.name,
            })
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(manifest), "output": str(DATA_DIR)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
