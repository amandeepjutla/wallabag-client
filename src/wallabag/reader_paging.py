# Kera (GPT-6 Astra). Created 2026-11-13.
"""Bounded list-page loading for the terminal reader."""
from dataclasses import dataclass
from typing import Optional

from wallabag.entry import Entry

PAGE_SIZE = 100


@dataclass
class EntryPage:
    entries: list[Entry]
    next_page: Optional[int]
    total: Optional[int]


def _number(payload: dict, name: str, minimum: int) -> Optional[int]:
    value = payload.get(name)
    if value is None:
        return None
    if type(value) is not int or value < minimum:
        raise ValueError(f"The server returned invalid article pagination ({name}).")
    return value


def parse_page(payload: dict, requested_page: int) -> EntryPage:
    if not isinstance(payload, dict) or not isinstance(payload.get("_embedded"), dict):
        raise ValueError("The server returned an invalid article list.")
    items = payload["_embedded"].get("items")
    if not isinstance(items, list):
        raise ValueError("The server returned an invalid article list.")
    page = _number(payload, "page", 1)
    if page is not None and page != requested_page:
        raise ValueError("The server returned a different article page. Press R to refresh.")
    pages = _number(payload, "pages", 0)
    total = _number(payload, "total", 0)
    limit = _number(payload, "limit", 1) or PAGE_SIZE
    entries, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or type(item.get("id")) not in (int, str):
            raise ValueError("The server returned an invalid article identifier.")
        entry = Entry(item)
        key = str(entry.entry_id)
        if key not in seen:
            entries.append(entry)
            seen.add(key)
    if pages is not None:
        more = requested_page < pages
    elif total is not None:
        more = requested_page * limit < total
    else:
        more = len(items) >= limit
    # An empty page is a bounded end even if concurrent changes made totals stale.
    return EntryPage(entries, requested_page + 1 if items and more else None, total)
