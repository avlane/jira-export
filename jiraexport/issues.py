"""Fetching issues by JQL."""

DEFAULT_FIELDS = ("summary", "issuetype", "status", "priority", "assignee", "reporter", "created", "updated",
                  "resolution", "labels", "components", "fixVersions", "project", "description")


def search(client, jql, fields=DEFAULT_FIELDS, expand=(), page_size=100):
    """Yield every issue matching the JQL, paging with startAt until total is reached."""
    start = 0
    while True:
        params = {"jql": jql, "startAt": start, "maxResults": page_size, "fields": ",".join(fields)}
        if expand:
            params["expand"] = ",".join(expand)
        data = client.get("search", params)
        batch = data["issues"]
        for issue in batch:
            yield issue
        start += len(batch)
        if not batch or start >= data["total"]:
            return
