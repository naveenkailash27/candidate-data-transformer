from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldValue:
    value: Any
    method: str


@dataclass
class SourceRecord:
    source: str
    record_id: str
    fields: dict[str, FieldValue]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionFailure:
    source: str
    location: str
    reason: str
