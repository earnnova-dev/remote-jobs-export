"""Command-line interface for remote-jobs-export."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional

from . import __version__
from .exporter import (
    DEFAULT_BASE,
    FetchError,
    export_csv,
    export_json,
    export_sqlite,
    fetch_jobs,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="remote-jobs-export",
        description="Pull, filter, and export normalized remote-job data "
        "from the free Remote Jobs API to CSV / JSON / SQLite.",
    )
    p.add_argument("--base", default=DEFAULT_BASE, help="API base URL (default: %(default)s)")
    p.add_argument("--api-key", default=None, help="Optional paid API key (free tier needs none)")
    p.add_argument("--skills", default=None, help="Comma-separated skill filter (e.g. python,devops)")
    p.add_argument("--source", default=None, help="Filter to one source (remotive/remoteok/jobicy/wwr/hn)")
    p.add_argument("--min-score", type=int, default=None, help="Minimum skill fit-score (0-100)")
    p.add_argument("--min-salary", type=int, default=None, help="Minimum salary (server-side filter on the parsed top-of-range salary_max; e.g. 90000 = $90k)")
    p.add_argument("--limit", type=int, default=100, help="Max jobs to fetch (default: %(default)s)")
    p.add_argument("--timeout", type=float, default=30.0, help="Request timeout seconds")
    p.add_argument("-o", "--output", default=None, help="Output file (implies format from extension)")
    p.add_argument(
        "--format",
        choices=["csv", "json", "sqlite"],
        default=None,
        help="Output format (default: inferred from --output extension; 'summary' via --summary)",
    )
    p.add_argument("--summary", action="store_true", help="Print a JSON summary and exit")
    p.add_argument("--version", action="version", version=f"%(prog) {__version__}")
    return p


def _format_from_output(path: str) -> str:
    if path.endswith(".csv"):
        return "csv"
    if path.endswith(".json"):
        return "json"
    if path.endswith(".db") or path.endswith(".sqlite") or path.endswith(".sqlite3"):
        return "sqlite"
    raise SystemExit(f"Cannot infer format from output extension: {path}")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else None

    try:
        jobs = fetch_jobs(
            base=args.base,
            api_key=args.api_key,
            skills=skills,
            source=args.source,
            min_score=args.min_score,
            min_salary=args.min_salary,
            limit=args.limit,
            timeout=args.timeout,
        )
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.summary:
        print(json.dumps(summarize(jobs), indent=2))
        return 0

    fmt = args.format or (
        _format_from_output(args.output) if args.output else "json"
    )
    if not args.output:
        if fmt == "json":
            print(json.dumps(jobs, ensure_ascii=False, indent=2))
        elif fmt == "csv":
            import csv
            import io

            buf = io.StringIO()
            from .exporter import COLUMNS, _row_for_csv

            w = csv.DictWriter(buf, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
            w.writeheader()
            for j in jobs:
                w.writerow(_row_for_csv(j))
            print(buf.getvalue(), end="")
        else:
            raise SystemExit("sqlite export requires --output <file>")
        return 0

    generated_at = int(time.time())
    if fmt == "csv":
        n = export_csv(jobs, args.output)
    elif fmt == "json":
        n = export_json(jobs, args.output, generated_at=generated_at)
    else:
        n = export_sqlite(jobs, args.output)
    print(f"exported {n} jobs -> {args.output} ({fmt})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
