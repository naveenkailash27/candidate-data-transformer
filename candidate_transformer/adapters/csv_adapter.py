from __future__ import annotations

import csv
from pathlib import Path

from ..models import Method
from .base import ExtractionFailure, FieldValue, SourceRecord

SOURCE = "csv"
_DM = Method.DIRECT_MAPPING.value


def extract_csv(path: str | Path) -> list[SourceRecord] | ExtractionFailure:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return ExtractionFailure(SOURCE, str(path), f"unreadable: {exc}")

    try:
        rows = list(csv.DictReader(text.splitlines()))
    except csv.Error as exc:
        return ExtractionFailure(SOURCE, str(path), f"malformed csv: {exc}")

    return [_row_to_record(row, i) for i, row in enumerate(rows)]


def _row_to_record(row: dict, idx: int) -> SourceRecord:
    def g(key: str) -> str:
        return (row.get(key) or "").strip()

    fields: dict[str, FieldValue] = {}
    if g("name"):
        fields["full_name"] = FieldValue(g("name"), _DM)
    if g("email"):
        fields["emails"] = FieldValue([g("email")], _DM)
    if g("phone"):
        fields["phones"] = FieldValue([g("phone")], _DM)

    company, title = g("current_company"), g("title")
    if company or title:
        fields["experience"] = FieldValue(
            [{"company": company or None, "title": title or None, "ongoing": True}], _DM
        )

    return SourceRecord(SOURCE, f"csv:{idx}", fields, raw=dict(row))
