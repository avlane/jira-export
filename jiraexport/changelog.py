"""Issue history: one row per changed field."""
from .flatten import normalise_timestamp

PAGE = 100
COLUMNS = ("issue", "history", "author", "created", "field", "fieldtype", "from", "fromString", "to", "toString")


def fetch(client, issue):
    """All histories of an issue. A search with expand=changelog embeds only the first page."""
    block = issue.get("changelog") or {}
    histories = list(block.get("histories", []))
    total = block.get("total", len(histories))
    while len(histories) < total:
        data = client.get("issue/{}/changelog".format(issue["key"]), {"startAt": len(histories), "maxResults": PAGE})
        page = data.get("values", [])
        if not page:
            break
        histories.extend(page)
        if data.get("isLast"):
            break
    return histories


def rows(issue_key, histories):
    out = []
    for history in histories:
        for item in history.get("items", []):
            out.append({"issue": issue_key, "history": history["id"],
                        "author": (history.get("author") or {}).get("displayName", ""),
                        "created": normalise_timestamp(history.get("created")), "field": item.get("field", ""),
                        "fieldtype": item.get("fieldtype", ""), "from": item.get("from") or "", "fromString": item.get("fromString") or "",
                        "to": item.get("to") or "", "toString": item.get("toString") or ""})
    return out
