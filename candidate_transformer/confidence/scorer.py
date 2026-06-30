from __future__ import annotations

FIELD_WEIGHTS = {
    "full_name": 3.0,
    "emails": 3.0,
    "phones": 2.0,
    "skills": 2.0,
    "experience": 2.0,
    "location": 1.0,
    "headline": 1.0,
    "education": 1.0,
    "links": 1.0,
    "years_experience": 1.0,
}

REQUIRED_FIELDS = {"full_name", "emails"}


def agreement_confidence(n_sources: int, conflict: bool) -> float:
    if conflict:
        return 0.5
    if n_sources <= 1:
        return 0.7
    return round(min(0.95, 0.8 + 0.05 * (n_sources - 1)), 2)


def overall_confidence(field_conf: dict[str, float], present: set[str]) -> float:
    keys = present | REQUIRED_FIELDS
    denom = 0.0
    numer = 0.0
    for f in keys:
        weight = FIELD_WEIGHTS.get(f, 1.0)
        denom += weight
        if f in present:
            numer += weight * field_conf.get(f, 0.0)
    return round(numer / denom, 2) if denom else 0.0
