from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparser

PRESENT_TOKENS = {"present", "current", "now", "ongoing", "till date", "to date", "till now"}

_ANCHOR = datetime(1900, 1, 1)


def is_present(raw: object) -> bool:
    return raw is not None and str(raw).strip().lower() in PRESENT_TOKENS


def normalize_month(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or is_present(text):
        return None

    m = re.fullmatch(r"(\d{1,2})[/-](\d{4})", text)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"(\d{4})[/-](\d{1,2})", text)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"

    if text.isdigit() and len(text) == 4:
        return f"{text}-01"
    try:
        dt = dateparser.parse(text, default=_ANCHOR)
    except (ValueError, OverflowError, TypeError):
        return None
    return f"{dt.year:04d}-{dt.month:02d}"
