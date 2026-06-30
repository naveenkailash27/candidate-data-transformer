from __future__ import annotations

import re

from ..models import CanonicalProfile
from ..normalize.registry import get_normalizer
from .config import ProjectionConfig
from .validator import validate

MISSING = object()

_SEGMENT = re.compile(r"^([A-Za-z_]\w*)?(\[\d+\]|\[\])?$")


class ConfigError(Exception):
    pass


class ProjectionError(Exception):
    pass


def _tokenize(expr: str) -> list[tuple[str | None, object]]:
    tokens: list[tuple[str | None, object]] = []
    for part in expr.split("."):
        m = _SEGMENT.match(part)
        if not m or (not m.group(1) and not m.group(2)):
            raise ConfigError(f"malformed path segment: '{part}' in '{expr}'")
        bracket_raw = m.group(2)
        if bracket_raw == "[]":
            bracket: object = "map"
        elif bracket_raw:
            bracket = int(bracket_raw[1:-1])
        else:
            bracket = None
        tokens.append((m.group(1), bracket))
    return tokens


def _walk(current: object, tokens: list[tuple[str | None, object]]):
    if not tokens:
        return MISSING if current is None else current

    (key, bracket), rest = tokens[0], tokens[1:]

    if key:
        if current is None:
            return MISSING
        if not isinstance(current, dict):
            raise ConfigError(f"cannot resolve '{key}' on non-object")
        if key not in current:
            raise ConfigError(f"unknown field '{key}'")
        current = current[key]

    if bracket is None:
        return _walk(current, rest)
    if bracket == "map":
        if current is None:
            return MISSING
        if not isinstance(current, list):
            raise ConfigError("'[]' applied to non-array")
        out = []
        for item in current:
            r = _walk(item, rest)
            if r is not MISSING and r is not None:
                out.append(r)
        return out
    if current is None:
        return MISSING
    if not isinstance(current, list):
        raise ConfigError("index applied to non-array")
    if bracket >= len(current):
        return MISSING
    return _walk(current[bracket], rest)


def _resolve(data: dict, expr: str):
    return _walk(data, _tokenize(expr))


def _apply_normalize(value: object, name: str):
    fn = get_normalizer(name)
    if fn is None:
        raise ConfigError(f"unknown normalizer: '{name}'")
    if isinstance(value, list):
        return [r for r in (fn(v) for v in value) if r is not None]
    r = fn(value)
    return MISSING if r is None else r


def project_profile(profile: CanonicalProfile, config: ProjectionConfig) -> dict:
    data = profile.model_dump()
    out: dict = {}

    for spec in config.fields:
        value = _resolve(data, spec.from_ or spec.path)
        if value is not MISSING and spec.normalize:
            value = _apply_normalize(value, spec.normalize)

        if value is MISSING:
            if spec.required:
                raise ProjectionError(f"required field missing: '{spec.path}'")
            if config.on_missing == "error":
                raise ProjectionError(f"missing field: '{spec.path}'")
            if config.on_missing == "omit":
                continue
            out[spec.path] = None
            continue

        out[spec.path] = value

    validate(out, config)

    if config.include_confidence:
        out["overall_confidence"] = profile.overall_confidence
    if config.include_provenance:
        out["provenance"] = [p.model_dump() for p in profile.provenance]

    return out


def default_projection(profile: CanonicalProfile) -> dict:
    return profile.model_dump()
