"""Run an export: search, flatten, collect extras, hand rows to the sinks."""
from collections import namedtuple

from . import issues
from .flatten import flatten

# fields: extra search fields; collect(client, issue) -> list of rows
Extra = namedtuple("Extra", "name fields columns collect expand", defaults=((),))


def export(client, jql, main_sink, extras=(), side_sinks=None, nested=False, fields=issues.DEFAULT_FIELDS, observe=None, skip=None, custom=()):
    """Write every matching issue to main_sink; return how many were written.

    With nested=True each extra's rows are stored inside the issue row (JSON
    formats). Otherwise they go to side_sinks[extra.name], one flat file each.
    """
    wanted = tuple(fields) + tuple(f.id for f in custom) + tuple(f for extra in extras for f in extra.fields)
    expand = tuple(e for extra in extras for e in extra.expand)
    for issue in issues.search(client, jql, fields=wanted, expand=expand):
        if skip is not None and skip(issue):
            continue
        row = flatten(issue, custom)
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
    return main_sink.count
