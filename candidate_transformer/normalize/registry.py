from __future__ import annotations

from typing import Callable

from .country import to_iso3166
from .dates import normalize_month
from .phone import normalize_phone
from .skills import canonical_skill

REGISTRY: dict[str, Callable[[object], object]] = {
    "E164": lambda v: normalize_phone(v),
    "date": normalize_month,
    "YYYY-MM": normalize_month,
    "ISO3166": to_iso3166,
    "canonical": canonical_skill,
}


def get_normalizer(name: str) -> Callable[[object], object] | None:
    return REGISTRY.get(name)
