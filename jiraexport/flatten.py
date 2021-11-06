"""Turn a raw issue into a flat row of strings."""
import re

from .adf import to_text

COLUMNS = ("key", "summary", "issuetype", "status", "priority", "assignee", "reporter", "created", "updated",
           "resolution", "labels", "components", "fixVersions", "project", "description")


def _name(obj):
    return (obj or {}).get("name", "")


def _person(user):
    return (user or {}).get("displayName", "")


def _names(items):
    return ", ".join(i.get("name", "") for i in items or [])


def flatten(issue):
    f = issue["fields"]
    return {
        "key": issue["key"],
        "summary": f.get("summary") or "",
        "issuetype": _name(f.get("issuetype")),
        "status": _name(f.get("status")),
        "priority": _name(f.get("priority")),
        "assignee": _person(f.get("assignee")),
        "reporter": _person(f.get("reporter")),
        "created": normalise_timestamp(f.get("created")),
        "updated": normalise_timestamp(f.get("updated")),
        "resolution": _name(f.get("resolution")),
        "labels": ", ".join(f.get("labels") or []),
        "components": _names(f.get("components")),
        "fixVersions": _names(f.get("fixVersions")),
        "project": (f.get("project") or {}).get("key", ""),
        "description": to_text(f.get("description")),
    }


_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")


def normalise_timestamp(value):
    """Jira writes offsets as +0000; ISO 8601 (and pandas, and Excel's importers) want +00:00."""
    return _OFFSET.sub(r"\1:\2", value) if value else ""
