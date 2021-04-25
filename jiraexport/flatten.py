"""Turn a raw issue into a flat row of strings."""
import json

COLUMNS = ("key", "summary", "issuetype", "status", "priority", "assignee", "reporter", "created", "updated",
           "resolution", "labels", "components", "fixVersions", "project", "description")


def _name(obj):
    return (obj or {}).get("name", "")


def _person(user):
    return (user or {}).get("displayName", "")


def _names(items):
    return ", ".join(i.get("name", "") for i in items or [])


def _description(value):
    if isinstance(value, dict):  # Atlassian Document Format; kept as JSON for now
        return json.dumps(value, sort_keys=True)
    return value or ""


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
        "created": f.get("created") or "",
        "updated": f.get("updated") or "",
        "resolution": _name(f.get("resolution")),
        "labels": ", ".join(f.get("labels") or []),
        "components": _names(f.get("components")),
        "fixVersions": _names(f.get("fixVersions")),
        "project": (f.get("project") or {}).get("key", ""),
        "description": _description(f.get("description")),
    }
