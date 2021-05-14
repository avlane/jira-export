"""Output formats."""
import csv


def write_csv(rows, columns, stream):
    writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    return count
