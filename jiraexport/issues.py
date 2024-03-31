"""Fetching issues by JQL."""

DEFAULT_FIELDS = ("summary", "issuetype", "status", "priority", "assignee", "reporter", "created", "updated",
                  "resolution", "labels", "components", "fixVersions", "project", "description", "parent", "subtasks", "timeoriginalestimate", "timeestimate", "timespent")

# GET puts the JQL in the URL; past roughly this length proxies and Jira start answering 414 or 400.
MAX_GET_JQL = 1500


def search(client, jql, fields=DEFAULT_FIELDS, expand=(), page_size=100):
    """Yield every issue matching the JQL, paging with startAt until total is reached.

    Long queries (for example an `issue in (...)` list) are sent as a POST body.
    """
    start = 0
    use_post = len(jql) > MAX_GET_JQL
    while True:
        if use_post:
            body = {"jql": jql, "startAt": start, "maxResults": page_size, "fields": list(fields)}
            if expand:
                body["expand"] = list(expand)
            data = client.request("POST", "search", body=body)
        else:
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
