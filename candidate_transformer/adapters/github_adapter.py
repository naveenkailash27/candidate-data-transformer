from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from ..models import Method
from .base import ExtractionFailure, FieldValue, SourceRecord

SOURCE = "github"
_DM = Method.DIRECT_MAPPING.value


def login_from_url(url: str) -> str | None:
    path = urlparse(url.strip()).path.strip("/")
    return path.split("/")[0] if path else None


def extract_github(url: str, fixtures_dir: str | Path) -> SourceRecord | ExtractionFailure:
    login = login_from_url(url)
    if not login:
        return ExtractionFailure(SOURCE, url, "unparseable github url")

    p = Path(fixtures_dir) / f"{login}.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        return ExtractionFailure(SOURCE, url, f"profile fixture missing for {login}")
    except json.JSONDecodeError as exc:
        return ExtractionFailure(SOURCE, url, f"malformed json: {exc}")

    return _data_to_record(data, login, url)


def _parse_location(text: str) -> dict:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 3:
        return {"city": parts[0], "region": parts[1], "country": parts[2]}
    if len(parts) == 2:
        return {"city": parts[0], "region": None, "country": parts[1]}
    return {"city": parts[0], "region": None, "country": None}


def _data_to_record(data: dict, login: str, url: str) -> SourceRecord:
    def g(key: str) -> str:
        return (data.get(key) or "").strip()

    fields: dict[str, FieldValue] = {}
    if g("name"):
        fields["full_name"] = FieldValue(g("name"), _DM)
    if g("email"):
        fields["emails"] = FieldValue([g("email")], _DM)
    if g("bio"):
        fields["headline"] = FieldValue(g("bio"), _DM)

    links = {"github": g("html_url") or url.strip()}
    if g("blog"):
        links["portfolio"] = g("blog")
    fields["links"] = FieldValue(links, _DM)

    if g("location"):
        fields["location"] = FieldValue(_parse_location(g("location")), _DM)

    languages = data.get("languages") or []
    if languages:
        fields["skills"] = FieldValue(list(languages), _DM)

    if g("company"):
        fields["experience"] = FieldValue(
            [{"company": g("company"), "title": None, "ongoing": True}], _DM
        )

    return SourceRecord(SOURCE, f"github:{login}", fields, raw=data)
