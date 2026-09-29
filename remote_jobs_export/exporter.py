"""Core: fetch + normalize + export remote-job data (stdlib only).

The free Remote Jobs API (default base) requires no key. A paid key is
optional and passed as ``api_key`` for higher limits / extra filters.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_BASE = "https://remote-jobs-api.tten.no"
DEFAULT_LIMIT = 100
USER_AGENT = "remote-jobs-export/1.0 (+https://github.com/earnnova-dev/remote-jobs-export)"

# Canonical export columns (stable order). ``published``/``salary`` may be "".
COLUMNS = [
    "id",
    "title",
    "company",
    "location",
    "category",
    "source",
    "salary",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "tags",
    "fit_score",
    "published",
    "url",
    "description",
]


class FetchError(RuntimeError):
    """Raised when the API request fails or returns an error payload."""


def _http_get(url: str, timeout: float = 30.0, api_key: Optional[str] = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:  # noqa: SIM105
        body = e.read().decode("utf-8", "replace")
        raise FetchError(f"HTTP {e.code} from {url}: {body[:200]}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"URLError from {url}: {e.reason}") from e


def fetch_jobs(
    base: str = DEFAULT_BASE,
    api_key: Optional[str] = None,
    skills: Optional[List[str]] = None,
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    min_salary: Optional[int] = None,
    limit: int = DEFAULT_LIMIT,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Fetch a list of normalized job dicts from the API (keyless by default).

    Returns a list of dicts with the :data:`COLUMNS` keys (missing fields
    coerced to ``""`` / ``[]`` / ``None``).
    """
    params: Dict[str, Any] = {"limit": max(1, int(limit))}
    if skills:
        params["skills"] = ",".join(skills)
    if source:
        params["source"] = source
    if min_score is not None:
        params["min_score"] = int(min_score)
    if min_salary is not None:
        params["min_salary"] = int(min_salary)
    qs = urllib.parse.urlencode(params)
    url = f"{base.rstrip('/')}/v1/jobs?{qs}"
    raw = _http_get(url, timeout=timeout, api_key=api_key)
    payload = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(payload, dict) or "jobs" not in payload:
        raise FetchError(f"Unexpected API response (no 'jobs' key): {str(payload)[:200]}")
    return [normalize_job(j) for j in payload["jobs"]]


def normalize_job(j: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce one API job dict to a stable, export-ready row."""
    tags = j.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    else:
        tags = [str(t).strip() for t in tags if str(t).strip()]
    # Dedupe tags, preserving first-seen order.
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]
    return {
        "id": j.get("id", ""),
        "title": (j.get("title") or "").strip(),
        "company": (j.get("company") or "").strip(),
        "location": (j.get("location") or "").strip(),
        "category": (j.get("category") or "").strip(),
        "source": (j.get("source") or "").strip(),
        "salary": (j.get("salary") or "").strip(),
        "salary_min": j.get("salary_min"),
        "salary_max": j.get("salary_max"),
        "salary_currency": (j.get("salary_currency") or "").strip(),
        "salary_period": (j.get("salary_period") or "").strip(),
        "tags": tags,
        "fit_score": j.get("fit_score"),
        "published": (j.get("published") or "").strip(),
        "url": (j.get("url") or "").strip(),
        "description": (j.get("description") or "").strip(),
    }


def _row_for_csv(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "category": job["category"],
        "source": job["source"],
        "salary": job["salary"],
        "salary_min": job["salary_min"],
        "salary_max": job["salary_max"],
        "salary_currency": job["salary_currency"],
        "salary_period": job["salary_period"],
        "tags": ",".join(job["tags"]),
        "fit_score": job["fit_score"],
        "published": job["published"],
        "url": job["url"],
        "description": job["description"],
    }


def export_csv(jobs: List[Dict[str, Any]], path: str) -> int:
    """Write jobs to a CSV file. Returns the number of rows written."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for job in jobs:
            w.writerow(_row_for_csv(job))
    return len(jobs)


def export_json(jobs: List[Dict[str, Any]], path: str, generated_at: Optional[int] = None) -> int:
    """Write jobs to a JSON file ({"exported_at":..., "count":..., "jobs":[...]})
    and return the number of rows written."""
    out = {
        "exported_at": generated_at,
        "count": len(jobs),
        "jobs": jobs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return len(jobs)


def export_sqlite(jobs: List[Dict[str, Any]], path: str, table: str = "jobs") -> int:
    """Write jobs into a SQLite DB (replaces the table). Returns rows written.

    ``tags`` is stored as a JSON array text; ``fit_score`` as INTEGER or NULL.
    """
    cols = {
        "id": "TEXT PRIMARY KEY",
        "title": "TEXT",
        "company": "TEXT",
        "location": "TEXT",
        "category": "TEXT",
        "source": "TEXT",
        "salary": "TEXT",
        "salary_min": "INTEGER",
        "salary_max": "INTEGER",
        "salary_currency": "TEXT",
        "salary_period": "TEXT",
        "tags": "TEXT",
        "fit_score": "INTEGER",
        "published": "TEXT",
        "url": "TEXT",
        "description": "TEXT",
    }
    col_list = ", ".join(f"{c} {t}" for c, t in cols.items())
    with sqlite3.connect(path) as con:
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} ({col_list})")
        insert = (
            f"INSERT INTO {table} "
            f"({', '.join(cols.keys())}) VALUES "
            f"({', '.join('?' for _ in cols)})"
        )
        rows = [
            (
                j["id"], j["title"], j["company"], j["location"], j["category"],
                j["source"], j["salary"], j["salary_min"], j["salary_max"],
                j["salary_currency"], j["salary_period"],
                json.dumps(j["tags"], ensure_ascii=False),
                j["fit_score"], j["published"], j["url"], j["description"],
            )
            for j in jobs
        ]
        con.executemany(insert, rows)
        con.commit()
    return len(jobs)


def summarize(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a small summary: total, by_source, by_category, top locations.

    Pure function over already-fetched (normalized) jobs; no I/O.
    """
    by_source: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    by_location: Dict[str, int] = {}
    scored = 0
    for j in jobs:
        s = j["source"] or "(none)"
        by_source[s] = by_source.get(s, 0) + 1
        c = j["category"] or "(none)"
        by_category[c] = by_category.get(c, 0) + 1
        loc = j["location"] or "(none)"
        by_location[loc] = by_location.get(loc, 0) + 1
        if j["fit_score"] is not None:
            scored += 1

    def top(d: Dict[str, int], n: int = 5):
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    return {
        "total": len(jobs),
        "by_source": top(by_source, 50),
        "by_category": top(by_category, 20),
        "top_locations": top(by_location, 10),
        "scored_jobs": scored,
    }
