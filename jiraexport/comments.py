"""Issue comments."""
from .adf import to_text
from .flatten import normalise_timestamp

PAGE = 100


def fetch(client, issue):
    """All comments of an issue. The search result embeds only the first page."""
    block = (issue.get("fields") or {}).get("comment") or {}
    comments = list(block.get("comments", []))
    total = block.get("total", len(comments))
    while len(comments) < total:
        data = client.get("issue/{}/comment".format(issue["key"]),
                          {"startAt": len(comments), "maxResults": PAGE, "orderBy": "created"})
        page = data.get("comments", [])
        if not page:
            break
        comments.extend(page)
    return comments


COLUMNS = ("issue", "id", "author", "created", "updated", "visibility", "body")


def rows(issue_key, comments):
    out = []
    for c in comments:
        visibility = c.get("visibility") or {}
        out.append({"issue": issue_key, "id": c["id"], "author": (c.get("author") or {}).get("displayName", ""),
                    "created": normalise_timestamp(c.get("created")), "updated": normalise_timestamp(c.get("updated")),
                    "visibility": visibility.get("value", ""), "body": to_text(c.get("body"))})
    return out
