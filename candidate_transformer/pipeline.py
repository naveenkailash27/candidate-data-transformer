from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .adapters.base import ExtractionFailure, SourceRecord
from .adapters.csv_adapter import extract_csv
from .adapters.github_adapter import extract_github
from .merge.merge import merge_records
from .models import CanonicalProfile
from .project.config import ProjectionConfig
from .project.projector import ProjectionError, default_projection, project_profile
from .project.validator import ValidationError


@dataclass
class RunResult:
    profiles: list[CanonicalProfile]
    projected: list[dict]
    source_failures: list[ExtractionFailure] = field(default_factory=list)
    projection_errors: list[dict] = field(default_factory=list)


def collect_records(inputs_dir: Path) -> tuple[list[SourceRecord], list[ExtractionFailure]]:
    records: list[SourceRecord] = []
    failures: list[ExtractionFailure] = []

    for csv_path in sorted(inputs_dir.glob("*.csv")):
        result = extract_csv(csv_path)
        if isinstance(result, ExtractionFailure):
            failures.append(result)
        else:
            records.extend(result)

    urls_file = inputs_dir / "github_urls.txt"
    if urls_file.exists():
        fixtures = inputs_dir / "github"
        for url in urls_file.read_text(encoding="utf-8").split():
            result = extract_github(url, fixtures)
            if isinstance(result, ExtractionFailure):
                failures.append(result)
            else:
                records.append(result)

    return records, failures


def run_pipeline(
    inputs_dir: str | Path,
    config: ProjectionConfig | None = None,
    reference: date | None = None,
) -> RunResult:
    records, failures = collect_records(Path(inputs_dir))
    profiles = merge_records(records, reference=reference)

    projected: list[dict] = []
    projection_errors: list[dict] = []
    for profile in profiles:
        try:
            if config is None:
                projected.append(default_projection(profile))
            else:
                projected.append(project_profile(profile, config))
        except (ProjectionError, ValidationError) as exc:
            projection_errors.append(
                {
                    "candidate_id": profile.candidate_id,
                    "full_name": profile.full_name,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                }
            )

    return RunResult(profiles, projected, failures, projection_errors)
