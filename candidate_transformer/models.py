from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Method(str, Enum):
    DIRECT_MAPPING = "direct_mapping"
    REGEX_EXTRACTION = "regex_extraction"
    MERGED_AGREEMENT = "merged_agreement"
    MERGED_CONFLICT_RESOLVED = "merged_conflict_resolved"
    NORMALIZED = "normalized"
    INFERRED_FALLBACK = "inferred_fallback"
    UNMATCHED_PASSTHROUGH = "unmatched_passthrough"
    INTERVAL_MERGE = "interval_merge"
    FLAGGED_MALFORMED = "flagged_malformed"


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str | None = None
    region: str | None = None
    country: str | None = None


class Links(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    confidence: float
    sources: list[str]
    method: str


class UnmatchedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    sources: list[str]
    confidence: float


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    title: str | None = None
    start: str | None = None
    end: str | None = None
    summary: str | None = None
    ongoing: bool = False


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    end_year: int | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    source: list[str]
    method: str


class CanonicalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = Field(default_factory=list)
    unmatched_skills: list[UnmatchedSkill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    overall_confidence: float = 0.0
