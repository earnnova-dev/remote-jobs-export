"""Offline tests for remote-jobs-export (no network)."""

import csv
import json
import os
import sqlite3
import tempfile

from remote_jobs_export import exporter
from remote_jobs_export.exporter import (
    COLUMNS,
    export_csv,
    export_json,
    export_sqlite,
    normalize_job,
    summarize,
)


def _sample_jobs():
    return [
        {
            "id": "a1",
            "title": "Python Engineer",
            "company": "Acme",
            "location": "Anywhere in the World",
            "category": "Back-end",
            "source": "wwr",
            "salary": "$100k",
            "tags": ["python", "django"],
            "fit_score": 80,
            "published": "2026-09-28T07:31:13+00:00",
            "url": "https://example.com/a1",
            "description": "desc a1",
        },
        {
            "id": "b2",
            "title": "Frontend Dev",
            "company": "Globex",
            "location": "US",
            "category": "Front-end",
            "source": "remotive",
            "salary": "",
            "tags": ["react"],
            "fit_score": None,
            "published": "",
            "url": "https://example.com/b2",
            "description": "desc b2",
        },
    ]


def test_normalize_fills_missing():
    row = normalize_job({"id": "x", "title": "T", "company": "C"})
    assert row["location"] == ""
    assert row["tags"] == []
    assert row["fit_score"] is None
    assert row["url"] == ""


def test_normalize_tags_string_to_list():
    row = normalize_job({"id": "x", "tags": "a, b, a"})
    assert row["tags"] == ["a", "b"]


def test_export_csv_roundtrip(tmp_path):
    p = str(tmp_path / "out.csv")
    n = export_csv(_sample_jobs(), p)
    assert n == 2
    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["title"] == "Python Engineer"
    assert rows[0]["tags"] == "python,django"
    assert set(rows[0].keys()) == set(COLUMNS)


def test_export_json_roundtrip(tmp_path):
    p = str(tmp_path / "out.json")
    n = export_json(_sample_jobs(), p, generated_at=123)
    assert n == 2
    data = json.load(open(p, encoding="utf-8"))
    assert data["count"] == 2
    assert data["exported_at"] == 123
    assert data["jobs"][0]["id"] == "a1"


def test_export_sqlite_roundtrip(tmp_path):
    p = str(tmp_path / "out.db")
    n = export_sqlite(_sample_jobs(), p)
    assert n == 2
    con = sqlite3.connect(p)
    cnt = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert cnt == 2
    one = con.execute("SELECT tags, fit_score FROM jobs WHERE id='b2'").fetchone()
    assert json.loads(one[0]) == ["react"]
    assert one[1] is None
    con.close()


def test_summarize_counts():
    s = summarize(_sample_jobs())
    assert s["total"] == 2
    src = dict(s["by_source"])
    assert src["wwr"] == 1 and src["remotive"] == 1
    loc = dict(s["top_locations"])
    assert loc["Anywhere in the World"] == 1
    assert s["scored_jobs"] == 1
