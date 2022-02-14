"""Issue worklogs."""
from .adf import to_text
from .flatten import normalise_timestamp

PAGE = 100
COLUMNS = ("issue", "id", "author", "started", "timeSpent", "timeSpentSeconds", "comment")


def fetch(client, issue):
    """All worklogs of an issue. The search result embeds only the first 20."""
    block = (issue.get("fields") or {}).get("worklog") or {}
    found = list(block.get("worklogs", []))
    total = block.get("total", len(found))
    while len(found) < total:
        data = client.get("issue/{}/worklog".format(issue["key"]), {"startAt": len(found), "maxResults": PAGE})
        page = data.get("worklogs", [])
        if not page:
            break
        found.extend(page)
    return found


def rows(issue_key, worklogs):
    return [{"issue": issue_key, "id": w["id"], "author": (w.get("author") or {}).get("displayName", ""),
             "started": normalise_timestamp(w.get("started")), "timeSpent": w.get("timeSpent", ""),
             "timeSpentSeconds": w.get("timeSpentSeconds", 0), "comment": to_text(w.get("comment"))} for w in worklogs]


def total_seconds(worklogs):
    return sum(w.get("timeSpentSeconds", 0) for w in worklogs)
