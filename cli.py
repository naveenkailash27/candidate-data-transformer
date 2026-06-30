from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from candidate_transformer.pipeline import run_pipeline
from candidate_transformer.project.config import load_config
from candidate_transformer.project.projector import ConfigError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--inputs", required=True, help="directory of input sources")
    parser.add_argument("--config", help="projection config JSON (default schema if omitted)")
    parser.add_argument("--out", help="output JSON path (stdout if omitted)")
    parser.add_argument("--reference", help="reference date YYYY-MM-DD for ongoing-role math")
    args = parser.parse_args(argv)

    config = None
    if args.config:
        try:
            config = load_config(args.config)
        except (ConfigError, ValueError) as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return 2

    reference = date.fromisoformat(args.reference) if args.reference else None

    try:
        result = run_pipeline(args.inputs, config=config, reference=reference)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(result.projected, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {len(result.projected)} profiles to {out_path}", file=sys.stderr)
    else:
        print(text)

    for f in result.source_failures:
        print(f"[skipped source] {f.source} {f.location}: {f.reason}", file=sys.stderr)
    for e in result.projection_errors:
        print(f"[projection error] {e['full_name']}: {e['detail']}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
