"""Offline tests for remote-jobs-export (no network)."""

import csv
import json
import os
import sqlite3
import tempfile

from remote_jobs_export import exporter
from remote_jobs_export.exporter import (
    COLUMNS,
    fetch_jobs,
    export_csv,
    export_json,
    export_sqlite,
    normalize_job,
    summarize,
)


def _sample_jobs():
    return [
        normalize_job({
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
            "salary_min": 100000,
            "salary_max": 120000,
            "salary_currency": "USD",
            "salary_period": "year",
        }),
        normalize_job({
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
        }),
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


def test_normalize_carries_structured_salary():
    row = normalize_job({
        "id": "s", "title": "T", "company": "C", "source": "wwr",
        "salary": "$100k-$120k", "salary_min": 100000, "salary_max": 120000,
        "salary_currency": "USD", "salary_period": "year", "tags": [],
        "fit_score": None, "published": "", "url": "u", "description": "d",
    })
    assert row["salary_min"] == 100000
    assert row["salary_max"] == 120000
    assert row["salary_currency"] == "USD"
    assert row["salary_period"] == "year"


def test_normalize_missing_salary_fields_default():
    row = normalize_job({"id": "x", "title": "T", "company": "C"})
    assert row["salary_min"] is None
    assert row["salary_max"] is None
    assert row["salary_currency"] == ""
    assert row["salary_period"] == ""


def test_export_sqlite_stores_salary(tmp_path):
    p = str(tmp_path / "out.db")
    export_sqlite(_sample_jobs(), p)
    con = sqlite3.connect(p)
    one = con.execute("SELECT salary_min, salary_max, salary_currency, salary_period FROM jobs WHERE id='a1'").fetchone()
    assert one == (100000, 120000, "USD", "year")
    con.close()


def test_fetch_passes_min_salary(tmp_path):
    captured = {}

    def fake_get(url, timeout=30.0, api_key=None):
        captured["url"] = url
        return b'{"jobs": []}'

    exporter._http_get = fake_get
    try:
        fetch_jobs(base="http://localhost", min_salary=90000, limit=10)
    finally:
        # restore
        import importlib
        importlib.reload(exporter)
    assert "min_salary=90000" in captured["url"]


def test_export_sqlite_empty_id_does_not_crash(tmp_path):
    # normalize_job defaults a missing id to ""; several such rows must not
    # violate the (former) UNIQUE id primary key.
    p = str(tmp_path / "out.db")
    jobs = [
        normalize_job({"title": "A", "company": "X"}),
        normalize_job({"title": "B", "company": "Y"}),
    ]
    n = export_sqlite(jobs, p)
    assert n == 2
    con = sqlite3.connect(p)
    cnt = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert cnt == 2
    titles = {r[0] for r in con.execute("SELECT title FROM jobs")}
    assert titles == {"A", "B"}
    con.close()


def test_export_sqlite_duplicate_id_does_not_crash(tmp_path):
    # A feed may carry two records with the same id; export must not raise.
    p = str(tmp_path / "out.db")
    jobs = [
        normalize_job({"id": "dup", "title": "First", "company": "X"}),
        normalize_job({"id": "dup", "title": "Second", "company": "Y"}),
    ]
    n = export_sqlite(jobs, p)
    assert n == 2
    con = sqlite3.connect(p)
    cnt = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assert cnt == 2
    # id lookup still works (now non-unique): returns both matching rows.
    dups = con.execute("SELECT COUNT(*) FROM jobs WHERE id='dup'").fetchone()[0]
    assert dups == 2
    con.close()
