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
| `-o`, `--output` | file to write; standard output if omitted. A name ending in `.gz` is compressed |
| `--incremental STATE` | export only what changed since the last run and append to `--output` (CSV or JSON Lines) |
| `-F`, `--field FIELD[=COLUMN]` | add a column for a custom field by id or name (repeatable) |
| `--manifest` | write `<output>.manifest.json` listing the files and row counts |
| `-f`, `--format` | `csv` (default), `json` (one array) or `jsonl` (one issue per line) |
| `--comments` | include every comment: `<output>-comments.csv` for CSV, nested in each issue for JSON |
| `--worklogs` | include every worklog, the same way |
| `--changelog` | include the change history (one row per changed field), the same way |
| `--attachments` | include attachment metadata, the same way |
| `--download-attachments DIR` | save the files under `DIR/<issue key>/` as `<id>-<filename>` |
| `--max-attachment-mb N` | skip downloading anything larger |

Rich text (descriptions, comments) is converted from Atlassian Document Format to plain
text. Timestamps are written as ISO 8601 with a colon in the offset.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens

Optional: `JIRA_TIMEOUT` (default 60 seconds per request) and `JIRA_MAX_RETRIES` (default 5;
applies to HTTP 429 and to 502/503/504 on reads).
