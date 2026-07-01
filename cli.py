from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from candidate_transformer.pipeline import RunResult, run_pipeline
from candidate_transformer.project.config import CANONICAL_FIELDS, ProjectionConfig, load_config
from candidate_transformer.project.projector import ConfigError


def _report(result: RunResult) -> None:
    for f in result.source_failures:
        print(f"[skipped source] {f.source} {f.location}: {f.reason}", file=sys.stderr)
    for e in result.projection_errors:
        print(f"[projection error] {e['full_name']}: {e['detail']}", file=sys.stderr)


def _emit(result: RunResult, out: str | None) -> None:
    text = json.dumps(result.projected, indent=2)
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {len(result.projected)} profiles to {out_path}", file=sys.stderr)
    else:
        print(text)


def _ask(prompt: str, default: str = "") -> str:
    try:
        value = input(prompt).strip()
    except EOFError:
        return default
    return value or default


def _build_config_interactively() -> ProjectionConfig:
    names = list(CANONICAL_FIELDS)
    print("Fields:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    picked = _ask("Include which fields? (comma numbers, or 'a' for all) [a]: ", "a")
    if picked.lower() in ("a", "all", ""):
        chosen = names
    else:
        idx = [int(x) for x in picked.replace(",", " ").split() if x.isdigit()]
        chosen = [names[i - 1] for i in idx if 1 <= i <= len(names)] or names

    on_missing = {"1": "null", "2": "omit", "3": "error"}.get(
        _ask("On missing value:  1) null   2) omit   3) error   [1]: ", "1"), "null"
    )
    include_provenance = _ask("Include provenance? [y/N]: ", "n").lower() in ("y", "yes")
    include_confidence = _ask("Include confidence? [y/N]: ", "n").lower() in ("y", "yes")

    return load_config(
        {
            "fields": [{"path": n, "type": CANONICAL_FIELDS[n]} for n in chosen],
            "on_missing": on_missing,
            "include_provenance": include_provenance,
            "include_confidence": include_confidence,
        }
    )


def run_interactive() -> int:
    print("=== Candidate Data Transformer (interactive) ===")

    inputs = _ask("Inputs folder [sample_inputs]: ", "sample_inputs")
    if not Path(inputs).exists():
        print(f"folder not found: {inputs}", file=sys.stderr)
        return 1

    config = None
    print("\nOutput shape:")
    print("  1. Default schema (full canonical profile)")
    print("  2. Load a config file")
    print("  3. Build a runtime config now (no file needed)")
    mode = _ask("Pick [1]: ", "1")

    try:
        if mode == "2":
            configs = sorted(Path("config").glob("*.json")) if Path("config").exists() else []
            for i, c in enumerate(configs, 1):
                print(f"  {i}. {c}")
            choice = _ask("Pick a number or type a path [1]: ", "1")
            cfg_path = configs[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(configs) else Path(choice)
            config = load_config(cfg_path)
        elif mode == "3":
            config = _build_config_interactively()
    except (ConfigError, ValueError, OSError, IndexError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    reference = None
    ref = _ask("Reference date YYYY-MM-DD [today]: ")
    if ref:
        try:
            reference = date.fromisoformat(ref)
        except ValueError:
            print("invalid date, using today", file=sys.stderr)

    try:
        result = run_pipeline(inputs, config=config, reference=reference)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    dest = _ask("Write to file (path) or leave blank to print: ")
    print()
    _emit(result, dest or None)
    _report(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--inputs", help="directory of input sources")
    parser.add_argument("--config", help="projection config JSON (default schema if omitted)")
    parser.add_argument("--out", help="output JSON path (stdout if omitted)")
    parser.add_argument("--reference", help="reference date YYYY-MM-DD for ongoing-role math")
    parser.add_argument("-i", "--interactive", action="store_true", help="prompt for inputs interactively")
    args = parser.parse_args(argv)

    if args.interactive or not args.inputs:
        return run_interactive()

    config = None
    if args.config:
        try:
            config = load_config(args.config)
        except (ConfigError, ValueError, OSError) as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return 2

    reference = date.fromisoformat(args.reference) if args.reference else None

    try:
        result = run_pipeline(args.inputs, config=config, reference=reference)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    _emit(result, args.out)
    _report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
