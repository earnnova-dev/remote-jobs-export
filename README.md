# remote-jobs-export

Pull, filter, and export normalized remote-job data from the **free [Remote Jobs API](https://remote-jobs-api.tten.no/)** to **CSV / JSON / SQLite** — or print a quick summary. **Stdlib-only** (no third-party dependencies), no API key required for the free tier.

The API aggregates 5 boards (Remotive, RemoteOK, Jobicy, We Work Remotely, Hacker News) into one clean schema. This tool pulls that data locally so you can analyze it in a spreadsheet, a database, or a script — no scraping, no key juggling.

## Why

- You want a snapshot of remote jobs as a **CSV** to open in Excel/Google Sheets.
- You want the data in **SQLite** for quick SQL analysis (`SELECT ... GROUP BY source`).
- You want a **JSON** file to feed into your own pipeline.
- You want a one-line **summary** (counts by source / category / location).

It's the offline, export-focused companion to the API itself.

## Install

```bash
pip install remote-jobs-export
```

Or run it directly from this repo without installing:

```bash
python -m remote_jobs_export.cli --help
```

## Quick start

```bash
# Export 100 jobs to a CSV file (no key needed)
remote-jobs-export --limit 100 -o jobs.csv

# Export to SQLite for SQL analysis
remote-jobs-export --limit 200 -o jobs.db

# Export to JSON
remote-jobs-export --limit 200 -o jobs.json

# Filter by source (remotive / remoteok / jobicy / wwr / hn)
remote-jobs-export --source remotive -o remotive.csv

# Filter by skills (comma-separated)
remote-jobs-export --skills python,devops -o python_devops.csv

# Filter by minimum skill fit-score (0-100) — requires --skills (the API
# only supports fit-score filtering for skill queries)
remote-jobs-export --skills python --min-score 70 -o top.csv

# Filter by minimum salary (server-side; on the parsed salary FLOOR salary_min)
remote-jobs-export --min-salary 90000 -o senior.csv

# Just print a summary (no file)
remote-jobs-export --limit 300 --summary
```

### Example summary output

The summary reflects the live feed as-is. Note that `category` is frequently
empty upstream (reported as `(none)` here) and `scored_jobs` is `0` for a plain
export — fit-scores are only computed by the API for skill queries
(`--skills`). The block below is a real capture of the quick-start command above:

```json
{
  "total": 300,
  "by_source": [["jobicy", 120], ["wwr", 83], ["remoteok", 81], ["remotive", 16]],
  "by_category": [["(none)", 201], ["Design", 11], ["Product", 10], ["Sales and Marketing", 10], ["All Other Remote", 9]],
  "top_locations": [["Anywhere in the World", 77], ["(none)", 32], ["USA / Senior", 17], ["USA / Director", 15], ["EMEA / Senior", 9]],
  "scored_jobs": 0
}
```

## Output schema (16 columns)

| column | type | notes |
|---|---|---|
| `id` | text | stable job id |
| `title` | text | |
| `company` | text | |
| `location` | text | may be empty |
| `category` | text | may be empty |
| `source` | text | `remotive` / `remoteok` / `jobicy` / `wwr` / `hn` |
| `salary` | text | raw string, may be empty |
| `salary_min` | int | parsed minimum salary, or null |
| `salary_max` | int | parsed maximum salary, or null |
| `salary_currency` | text | e.g. `USD`, may be empty |
| `salary_period` | text | e.g. `year` / `month` / `day`, may be empty |
| `tags` | CSV: comma-joined · JSON/SQLite: list | deduped, order-preserving |
| `fit_score` | int | 0-100, or null |
| `published` | text | ISO-8601 UTC or empty |
| `url` | text | original job listing URL |
| `description` | text | |

## Python API

```python
from remote_jobs_export import fetch_jobs, export_csv, export_sqlite, summarize

jobs = fetch_jobs(limit=200, skills=["python"], min_salary=90000)   # keyless free tier; filter by min salary
export_csv(jobs, "jobs.csv")
export_sqlite(jobs, "jobs.db")
print(summarize(jobs))
```

A paid `api_key` can be passed to `fetch_jobs(api_key=...)` (sent as `Authorization: Bearer ...`) for higher limits / extra filters.

## Notes

- **Free tier needs no key.** The default base (`https://remote-jobs-api.tten.no`) serves the free tier keyless.
- **Stdlib-only.** Python 3.8+. No `requests`, no `pandas`.
- **Idempotent.** Re-exporting to the same SQLite file replaces the `jobs` table.

## License

MIT
