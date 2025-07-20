"""Incremental exports: remember how far the previous run got."""
import json
import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger("jiraexport")

VERSION = 1


class StateError(Exception):
    pass


def load(path: str) -> dict | None:
    """The saved state, or None when the file does not exist yet."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except ValueError as exc:
        raise StateError("{} is not valid JSON: {}".format(path, exc))
    if data.get("version") != VERSION:
        raise StateError("{} has state version {!r}; expected {}".format(path, data.get("version"), VERSION))
    return data


def save(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def parse(stamp):
    return datetime.fromisoformat(stamp)


_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)


def split_order_by(jql: str) -> tuple[str, str]:
    """Split a query into (conditions, order clause), ignoring ORDER BY inside quoted strings."""
    quote = None
    for index, char in enumerate(jql):
        if quote:
            if char == quote and jql[index - 1] != "\\":
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "oO":
            found = _ORDER_BY.match(jql, index)
            if found and (index == 0 or not (jql[index - 1].isalnum() or jql[index - 1] == "_")):
                return jql[:index].strip(), jql[index:].strip()
    return jql.strip(), ""


def user_timezone(client) -> str | None:
    """The API user's time zone name, or None. JQL date literals are read in this zone."""
    return client.get("myself").get("timeZone")


def jql_since(jql: str, since: str, tz: str | None = None) -> str:
    """Narrow a query to issues updated at or after `since` (JQL only has minute precision).

    JQL reads "2025-03-01 09:30" in the *user's* time zone, so `since` is
    converted to the zone named by `tz` (from user_timezone) first.

    The original conditions are parenthesised so an OR cannot swallow the new
    clause, and any ORDER BY stays at the end where JQL requires it.
    """
    where, order = split_order_by(jql)
    moment = parse(since)
    if tz:
        try:
            moment = moment.astimezone(ZoneInfo(tz))
        except (ZoneInfoNotFoundError, ValueError):
            log.warning("unknown time zone %r; using the offset recorded with the timestamp", tz)
    clause = 'updated >= "{}"'.format(moment.strftime("%Y-%m-%d %H:%M"))
    narrowed = "({}) AND {}".format(where, clause) if where else clause
    return "{} {}".format(narrowed, order) if order else narrowed


def fresh(jql):
    return {"version": VERSION, "jql": jql, "last_updated": None, "seen": {}, "runs": 0, "exported": 0}


def minute_floor(stamp):
    return parse(stamp).replace(second=0, microsecond=0)


def already_exported(state, issue):
    """True for an issue the previous run wrote: the JQL window is inclusive and only minute-precise,
    so the last minute of the previous run is fetched again."""
    from .flatten import normalise_timestamp

    return state.get("seen", {}).get(issue["key"]) == normalise_timestamp(issue["fields"]["updated"])


def advance(state, issues, exported):
    """The state to save after a run that wrote `issues` (the raw issues exported)."""
    from .flatten import normalise_timestamp

    latest = state.get("last_updated")
    seen = dict(state.get("seen", {}))
    for issue in issues:
        stamp = normalise_timestamp(issue["fields"]["updated"])
        seen[issue["key"]] = stamp
        if latest is None or parse(stamp) > parse(latest):
            latest = stamp
    if latest is not None:  # only the final minute can be fetched twice
        floor = minute_floor(latest)
        seen = {key: stamp for key, stamp in seen.items() if parse(stamp) >= floor}
    return dict(state, last_updated=latest, seen=seen, runs=state.get("runs", 0) + 1, exported=state.get("exported", 0) + exported)
