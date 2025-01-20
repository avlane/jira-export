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
| `--jql` | the query that selects issues |
| `-p`, `--project KEY` | only this project (repeatable); combined with the other filters using AND |
| `--status NAME` | only this status (repeatable) |
| `--updated-since DATE` | only issues updated on or after `2024-03-01` or `2024-03-01 09:30` |
| `-o`, `--output` | file to write; standard output if omitted. A name ending in `.gz` is compressed |
| `--incremental STATE` | export only what changed since the last run and append to `--output` (CSV or JSON Lines) |
| `-F`, `--field FIELD[=COLUMN]` | add a column for a custom field by id or name (repeatable) |
| `--manifest` | write `<output>.manifest.json` listing the files and row counts |
| `--raw-csv` | do not put a quote in front of CSV cells that start with `=`, `+`, `@` or `-` (they are defused by default) |
| `--excel` | start CSV files with a UTF-8 byte order mark so Excel shows accents correctly |
| `--classic-search` | use the classic search endpoint instead of `search/jql` (Atlassian is retiring it) |
| `--limit N` | stop after N issues |
| `--columns A,B,C` | only these columns of the main file, in this order |
| `-f`, `--format` | `csv` (default), `json` (one array) or `jsonl` (one issue per line) |
| `--html` | add a `description_html` column with Jira's rendered HTML |
| `--comments` | include every comment: `<output>-comments.csv` for CSV, nested in each issue for JSON |
| `--worklogs` | include every worklog, the same way |
| `--changelog` | include the change history (one row per changed field), the same way |
| `--links` | include issue links, the same way |
| `--attachments` | include attachment metadata, the same way |
| `--download-attachments DIR` | save the files under `DIR/<issue key>/` as `<id>-<filename>` |
| `--download-workers N` | fetch an issue's attachments with N threads |
| `--max-attachment-mb N` | skip downloading anything larger |

## Output

With `--format csv` the main file has one row per issue. Comments, worklogs, the change history,
links and attachment metadata go to files next to it (`issues.csv` gives `issues-comments.csv`,
`issues-worklogs.csv`, `issues-changelog.csv`, `issues-links.csv` and `issues-attachments.csv`), each
row carrying the issue key. With `json` or `jsonl` they are nested inside each issue instead, so no
`--output` is needed.

Rich text (descriptions, comments) is converted from Atlassian Document Format to plain text.
Timestamps are ISO 8601 with a colon in the offset. Estimates are in seconds. Cells that could be
read as spreadsheet formulas get a leading quote unless you pass `--raw-csv`.

## Incremental exports

    jira-export -p PLAT -o plat.jsonl -f jsonl --incremental plat.state

The first run exports everything and records the newest `updated` time it saw. Later runs
only ask for issues updated since then and append them; issues from the final minute of the
previous run (JQL has minute precision) are skipped rather than written twice. Changing
the query starts again from the beginning.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens

Optional: `JIRA_TIMEOUT` (default 60 seconds per request) and `JIRA_MAX_RETRIES` (default 5;
applies to HTTP 429 and to 502/503/504 on reads).
