from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CANONICAL_FIELDS: dict[str, str] = {
    "candidate_id": "string",
    "full_name": "string",
    "emails": "string[]",
    "phones": "string[]",
    "location": "object",
    "links": "object",
    "headline": "string",
    "years_experience": "number",
    "skills": "object[]",
    "unmatched_skills": "object[]",
    "experience": "object[]",
    "education": "object[]",
}


class FieldSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    path: str
    from_: str | None = Field(default=None, alias="from")
    type: str
    required: bool = False
    normalize: str | None = None


class ProjectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldSpec]
    include_confidence: bool = False
    include_provenance: bool = False
    on_missing: Literal["null", "omit", "error"] = "null"


def load_config(source: str | Path | dict) -> ProjectionConfig:
    if isinstance(source, dict):
        return ProjectionConfig(**source)
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    return ProjectionConfig(**data)
