"""Run an export: search, flatten, collect extras, hand rows to the sinks."""
import logging
from collections import namedtuple
from collections.abc import Callable, Iterable

from . import issues
from .flatten import flatten

log = logging.getLogger("jiraexport")
PROGRESS_EVERY = 100

# fields: extra search fields; collect(client, issue) -> list of rows
Extra = namedtuple("Extra", "name fields columns collect expand", defaults=((),))


def export(client, jql: str, main_sink, extras: Iterable = (), side_sinks: dict | None = None, nested: bool = False,
           fields: tuple[str, ...] = issues.DEFAULT_FIELDS, observe: Callable | None = None, skip: Callable | None = None,
           custom: tuple = (), html: bool = False, limit: int | None = None, only: tuple[str, ...] | None = None,
           search: Callable = issues.search, estimate: int | None = None) -> int:
    """Write every matching issue to main_sink; return how many were written.

    With nested=True each extra's rows are stored inside the issue row (JSON
    formats). Otherwise they go to side_sinks[extra.name], one flat file each.
    """
    wanted = tuple(fields) + tuple(f.id for f in custom) + tuple(f for extra in extras for f in extra.fields)
    expand = tuple(e for extra in extras for e in extra.expand) + (("renderedFields",) if html else ())
    if estimate is not None:
        log.info("about %d issues match", estimate)
    for issue in search(client, jql, fields=wanted, expand=expand):
        if skip is not None and skip(issue):
            continue
        if limit is not None and main_sink.count >= limit:
            break
        row = flatten(issue, custom, html, typed=nested)
        if only:
            row = {name: row[name] for name in only}
        for extra in extras:
            found = extra.collect(client, issue)
            if nested:
                row[extra.name] = found
            else:
                for item in found:
                    side_sinks[extra.name].write(item)
        main_sink.write(row)
        if observe is not None:
            observe(issue)
        if main_sink.count % PROGRESS_EVERY == 0:
            if estimate:
                log.info("exported %d of about %d issues (last: %s)", main_sink.count, estimate, issue["key"])
            else:
                log.info("exported %d issues (last: %s)", main_sink.count, issue["key"])
    log.info("export finished: %d issues", main_sink.count)
    return main_sink.count
