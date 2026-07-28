from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from .schemas import Fact, FactResolution


def _value_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def resolve_facts(facts: list[Fact]) -> FactResolution:
    """Choose the latest recorded fact and retain conflicts instead of hiding them."""
    grouped: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        grouped[fact.field].append(fact)

    latest: dict[str, Fact] = {}
    conflicts: dict[str, list[str]] = {}
    for field, candidates in grouped.items():
        values = {_value_key(fact.value) for fact in candidates}
        if len(values) > 1:
            conflicts[field] = sorted(values)
        latest[field] = max(
            candidates,
            key=lambda fact: (
                fact.recorded_date or fact.event_date or date.min,
                fact.event_date or date.min,
            ),
        )
    return FactResolution(latest=latest, conflicts=conflicts)


def missing_facts(required: list[str], resolution: FactResolution) -> list[str]:
    return [field for field in required if field not in resolution.latest]
