"""Incremental exports: remember how far the previous run got."""
import json
import os
from datetime import datetime

VERSION = 1


class StateError(Exception):
    pass


def load(path):
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


def jql_since(jql, since):
    """Narrow a query to issues updated at or after `since` (JQL only has minute precision)."""
    return '{} AND updated >= "{}"'.format(jql, parse(since).strftime("%Y-%m-%d %H:%M"))


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
