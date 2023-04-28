"""Choosing extra (usually custom) fields by id or by name."""
import re
from collections import namedtuple

from .flatten import COLUMNS

Field = namedtuple("Field", "id column")


class FieldError(ValueError):
    pass


def slug(name):
    """'Story point estimate' -> 'story_point_estimate'."""
    return re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")


def parse_spec(spec):
    """'customfield_10016', 'Story point estimate' or either of those followed by '=column'."""
    key, _, column = spec.partition("=")
    return key.strip(), column.strip()


def resolve(client, specs):
    """Look the specs up in the site's field list and return Field(id, column) for each."""
    if not specs:
        return []
    available = client.get("field")
    by_id = {f["id"]: f for f in available}
    by_name = {f["name"].casefold(): f for f in available}
    chosen, used = [], set(COLUMNS)
    for spec in specs:
        key, column = parse_spec(spec)
        field = by_id.get(key) or by_name.get(key.casefold())
        if field is None:
            raise FieldError("no field {!r} on this site".format(key))
        column = column or slug(field["name"])
        if column in used:
            raise FieldError("column name {!r} is already taken; pick another with {}={}_2".format(column, key, column))
        used.add(column)
        chosen.append(Field(field["id"], column))
    return chosen
