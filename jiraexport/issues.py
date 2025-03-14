"""Fetching issues by JQL."""
import json
import logging

log = logging.getLogger("jiraexport")

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


def search_enhanced(client, jql, fields=DEFAULT_FIELDS, expand=(), page_size=100):
    """Yield issues through the enhanced search (search/jql).

    It pages with an opaque nextPageToken and returns no total. The request is
    always a POST, so long queries need no special case. In this endpoint
    `expand` is one comma-separated string rather than a list.
    """
    token = None
    while True:
        body = {"jql": jql, "maxResults": page_size, "fields": list(fields)}
        if expand:
            body["expand"] = ",".join(expand)
        if token:
            body["nextPageToken"] = token
        data = client.request("POST", "search/jql", body=body)
        for issue in data.get("issues", []):
            yield issue
        token = data.get("nextPageToken")
        if not token or data.get("isLast"):
            return


def approximate_count(client, jql):
    """Estimated number of matching issues. The enhanced search returns no total, so this is the only cheap way to know."""
    return client.request("POST", "search/approximate-count", body={"jql": jql})["count"]


BULK_LIMIT = 100


def bulk_fetch(client, ids, fields=DEFAULT_FIELDS, expand=()):
    """Fetch full issues by id or key with the bulk fetch endpoint. Returns (issues, errors); at most 100 ids."""
    if len(ids) > BULK_LIMIT:
        raise ValueError("bulk fetch takes at most {} issues".format(BULK_LIMIT))
    body = {"issueIdsOrKeys": list(ids), "fields": list(fields)}
    if expand:
        body["expand"] = list(expand)
    data = client.request("POST", "issue/bulkfetch", body=body)
    return data.get("issues", []), data.get("issueErrors", [])


def search_hydrated(client, jql, fields=DEFAULT_FIELDS, expand=(), page_size=100, failures=None):
    """Search for issue ids only, then fetch their content in batches.

    Keeps the search pages small and fast for exports with big fields (changelog,
    rendered HTML). Issues come back in search order. Ids the bulk fetch refuses
    are logged and, if a list is passed as `failures`, appended to it.
    """
    batch = []

    def flush():
        found, errors = bulk_fetch(client, [i["id"] for i in batch], fields, expand)
        for problem in errors:
            # An issue deleted or hidden between the search and the fetch must not sink the whole export.
            log.warning("could not fetch %s: %s", ", ".join(problem.get("issueIdsOrKeys", [])), problem.get("errorMessage") or json.dumps(problem)[:200])
            if failures is not None:
                failures.extend(problem.get("issueIdsOrKeys", []))
        by_id = {issue["id"]: issue for issue in found}
        return [by_id[i["id"]] for i in batch if i["id"] in by_id]

    for stub in search_enhanced(client, jql, fields=("id",), page_size=page_size):
        batch.append(stub)
        if len(batch) == BULK_LIMIT:
            yield from flush()
            batch = []
    if batch:
        yield from flush()
