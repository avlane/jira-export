"""Output formats."""
import csv
import json


def write_csv(rows, columns, stream):
    writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    return count


def write_json(rows, stream):
    """Write all rows as one JSON array."""
    rows = list(rows)
    json.dump(rows, stream, indent=2, ensure_ascii=False)
    stream.write("\n")
    return len(rows)


def writer_for(fmt):
    if fmt == "csv":
        return lambda rows, columns, stream: write_csv(rows, columns, stream)
    if fmt == "json":
        return lambda rows, columns, stream: write_json(rows, stream)
    raise ValueError("unknown format {!r}".format(fmt))
