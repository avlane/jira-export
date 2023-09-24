"""A small JSON file describing what an export contains."""
import json
import os
from datetime import datetime, timezone

from . import __version__


def build(jql, fmt, started, finished, files):
    """files maps each written path to the number of rows in it."""
    return {
        "tool": "jira-export", "version": __version__, "jql": jql, "format": fmt,
        "started": started.isoformat(timespec="seconds"), "finished": finished.isoformat(timespec="seconds"),
        "files": [{"path": os.path.basename(path), "rows": rows} for path, rows in files.items()],
    }


def write(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def now():
    return datetime.now(timezone.utc)
