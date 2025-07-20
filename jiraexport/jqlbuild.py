"""Build a JQL query from convenience options."""
import re

from .incremental import split_order_by

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")


class JqlError(ValueError):
    pass


def quote(value: str) -> str:
    return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))


def build(jql: str | None = None, projects: tuple | list = (), statuses: tuple | list = (),
          updated_since: str | None = None) -> str:
    """AND together an optional raw query and the convenience filters; ORDER BY stays last."""
    where, order = split_order_by(jql) if jql else ("", "")
    parts = ["({})".format(where)] if where else []
    if projects:
        parts.append("project in ({})".format(", ".join(quote(p) for p in projects)))
    if statuses:
        parts.append("status in ({})".format(", ".join(quote(s) for s in statuses)))
    if updated_since:
        if not _DATE.match(updated_since):
            raise JqlError("--updated-since must look like 2024-03-01 or '2024-03-01 09:30' (got {!r})".format(updated_since))
        parts.append("updated >= {}".format(quote(updated_since)))
    if not parts and not order:
        raise JqlError("give --jql, --project, --status or --updated-since")
    if jql and not (projects or statuses or updated_since):
        return jql.strip()  # nothing to combine with, so leave the query exactly as written
    query = " AND ".join(parts)
    return "{} {}".format(query, order).strip()
