from __future__ import annotations

from .config import ProjectionConfig

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "number[]": lambda v: isinstance(v, list) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "object[]": lambda v: isinstance(v, list) and all(isinstance(x, dict) for x in v),
}


class ValidationError(Exception):
    pass


def validate(out: dict, config: ProjectionConfig) -> dict:
    for spec in config.fields:
        present = spec.path in out
        value = out.get(spec.path)

        if spec.required and (not present or value is None):
            raise ValidationError(f"required field '{spec.path}' is missing or null")

        if present and value is not None:
            check = _TYPE_CHECKS.get(spec.type)
            if check is None:
                raise ValidationError(f"unknown type '{spec.type}' for '{spec.path}'")
            if not check(value):
                raise ValidationError(f"field '{spec.path}' expected {spec.type}, got {type(value).__name__}")

    return out
