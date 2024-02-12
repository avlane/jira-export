"""Turn a raw issue into a flat row of strings."""
import json
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


def render_value(value):
    """Text for one field value: strings and numbers as they are, option objects by their label."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(text for text in (render_value(v) for v in value) if text)
    if isinstance(value, dict):
        if value.get("type") == "doc":
            return to_text(value)
        for key in ("displayName", "value", "name"):
            if value.get(key):
                label = str(value[key])
                child = value.get("child")  # cascading select: "Hardware / Laptop"
                return "{} / {}".format(label, render_value(child)) if child else label
    return json.dumps(value, sort_keys=True)


def columns(custom=(), html=False):
    return COLUMNS + tuple(f.column for f in custom) + (("description_html",) if html else ())


def flatten(issue, custom=(), html=False):
    f = issue["fields"]
    row = _core(f, issue["key"])
    if html:  # needs expand=renderedFields
        row["description_html"] = (issue.get("renderedFields") or {}).get("description") or ""
    for field in custom:
        row[field.column] = render_value(f.get(field.id))
    return row


def _core(f, key):
    return {
        "key": key,
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
