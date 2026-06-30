from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "skills.json"


def _key(text: str) -> str:
    return "".join(ch for ch in text.lower().strip() if ch.isalnum() or ch in " +#.")


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    raw = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for canonical, aliases in raw.items():
        mapping[_key(canonical)] = canonical
        for alias in aliases:
            mapping[_key(alias)] = canonical
    return mapping


def canonical_skill(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return _alias_map().get(_key(text))
