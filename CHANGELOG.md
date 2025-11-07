# Changelog

## 1.0.0

- Searches use `search/jql` only; the classic search code is gone.
- `--bulk-fetch`, `--list-fields`, `--version`; progress shows an estimated total.
- Incremental runs convert the saved time to the API user's time zone.
- ADF: task lists, decisions, extensions; malformed documents no longer raise.
- JSON output keeps numbers and lists typed.

## 0.7

- `--incremental` with final-minute de-duplication, `--manifest`, gzip output, `--excel`.
- Spreadsheet formulas in CSV cells are defused (`--raw-csv` turns this off).
- Attachment downloads: resumable, concurrent, SHA-256 checksums, safe file names.

## 0.5

- Comments, worklogs, change history, links and attachments as sidecar CSV files or nested JSON.
- `--field`, `--columns`, `--limit`, `--project`, `--status`, `--updated-since`.

## 0.1

- JQL export to CSV and JSON with ADF converted to plain text.
