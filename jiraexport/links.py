"""Issue links (blocks, relates to, duplicates ...)."""

COLUMNS = ("issue", "id", "type", "direction", "relation", "other", "other_summary", "other_status")


def rows(issue_key, links):
    """One row per link, seen from this issue: `relation` reads as '<issue> <relation> <other>'."""
    out = []
    for link in links or []:
        kind = link.get("type") or {}
        if "outwardIssue" in link:
            direction, relation, other = "outward", kind.get("outward", ""), link["outwardIssue"]
        elif "inwardIssue" in link:
            direction, relation, other = "inward", kind.get("inward", ""), link["inwardIssue"]
        else:
            continue
        fields = other.get("fields") or {}
        out.append({"issue": issue_key, "id": link.get("id", ""), "type": kind.get("name", ""), "direction": direction,
                    "relation": relation, "other": other.get("key", ""), "other_summary": fields.get("summary", ""),
                    "other_status": (fields.get("status") or {}).get("name", "")})
    return out
