"""Output sinks. Rows are written as they arrive so large exports stay in constant memory."""
import csv
import json


class CsvSink:
    def __init__(self, stream, columns, header=True):
        self.writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
        if header:
            self.writer.writeheader()
        self.count = 0

    def write(self, row):
        self.writer.writerow(row)
        self.count += 1

    def close(self):
        pass


class JsonlSink:
    """One JSON object per line."""

    def __init__(self, stream, columns=None, header=True):
        self.stream = stream
        self.count = 0

    def write(self, row):
        self.stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.count += 1

    def close(self):
        pass


class JsonSink:
    """A single JSON array, written element by element."""

    def __init__(self, stream, columns=None, header=True):
        self.stream = stream
        self.count = 0

    def write(self, row):
        self.stream.write("[\n" if self.count == 0 else ",\n")
        self.stream.write(json.dumps(row, indent=2, ensure_ascii=False))
        self.count += 1

    def close(self):
        self.stream.write("\n]\n" if self.count else "[]\n")


def open_text(path, mode="w", bom=False):
    """Open a text file for writing or appending; a .gz name is compressed on the fly.

    bom=True starts a new file with a UTF-8 byte order mark, which makes Excel
    read it as UTF-8 instead of the local code page.
    """
    encoding = "utf-8-sig" if bom and mode == "w" else "utf-8"
    if path.endswith(".gz"):
        import gzip

        return gzip.open(path, {"w": "wt", "a": "at"}[mode], encoding=encoding, newline="")
    return open(path, mode, newline="", encoding=encoding)


NESTED = ("json", "jsonl")  # formats that can hold comments, worklogs and so on inside each issue
SINKS = {"csv": CsvSink, "json": JsonSink, "jsonl": JsonlSink}


def open_sink(fmt, stream, columns, header=True):
    """header=False is for appending to a CSV that already has one."""
    try:
        return SINKS[fmt](stream, columns, header)
    except KeyError:
        raise ValueError("unknown format {!r}".format(fmt))


def write_csv(rows, columns, stream):
    sink = CsvSink(stream, columns)
    for row in rows:
        sink.write(row)
    return sink.count
