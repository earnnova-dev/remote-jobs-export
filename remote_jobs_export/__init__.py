"""remote-jobs-export: pull, filter, and export normalized remote-job data.

Stdlib-only. Pulls from the free Remote Jobs API (no key required) and writes
to CSV / JSON / SQLite, or prints a summary. See README for usage.
"""

__version__ = "1.1.0"

from .exporter import (
    fetch_jobs,
    export_csv,
    export_json,
    export_sqlite,
    summarize,
)

__all__ = [
    "fetch_jobs",
    "export_csv",
    "export_json",
    "export_sqlite",
    "summarize",
    "__version__",
]
