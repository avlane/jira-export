# jira-export

Export Jira Cloud issues, selected with JQL, to CSV or JSON. It talks to the REST API
with an email address and an API token, and keeps the HTTP session injectable so the
tests can replay recorded JSON.

Status: just started. First goal is a flat CSV of the common fields, then comments,
changelog, worklogs and attachments.

## Usage

    python -m jiraexport --jql 'project = PLAT ORDER BY created' -o issues.csv

Options:

| option | meaning |
| --- | --- |
| `--jql` | the query that selects issues (required) |
| `-o`, `--output` | file to write; standard output if omitted |
| `-f`, `--format` | `csv` (default) or `json` |
| `--comments` | also write `<output>-comments.csv` with every comment |

Rich text (descriptions, comments) is converted from Atlassian Document Format to plain
text. Timestamps are written as ISO 8601 with a colon in the offset.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens
