"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import contextlib
import logging
import os
import sys

from . import attachments, changelog, comments, config, exporter, fieldmap, incremental, jqlbuild, links, manifest, worklogs, writers
from .client import JiraClient, JiraError
from .exporter import Extra
from .flatten import columns as flat_columns


def build_parser():
    parser = argparse.ArgumentParser(prog="jira-export", description="Export Jira Cloud issues selected by JQL.")
    parser.add_argument("--jql", help="JQL query selecting the issues")
    parser.add_argument("--project", "-p", action="append", default=[], metavar="KEY", help="only this project (repeatable)")
    parser.add_argument("--status", action="append", default=[], metavar="NAME", help="only this status (repeatable)")
    parser.add_argument("--updated-since", metavar="DATE", help="only issues updated on or after 2024-03-01 [HH:MM]")
    parser.add_argument("--output", "-o", help="file to write (default: standard output)")
    parser.add_argument("--format", "-f", choices=sorted(writers.SINKS), default="csv", help="output format (default csv)")
    parser.add_argument("--field", "-F", action="append", default=[], metavar="FIELD[=COLUMN]",
                        help="add a column for a field, by id or name (repeatable), e.g. 'Story point estimate=points'")
    parser.add_argument("--limit", type=int, metavar="N", help="stop after N issues")
    parser.add_argument("--columns", metavar="A,B,C", help="only these columns of the main file, in this order")
    parser.add_argument("--html", action="store_true", help="add a description_html column with Jira's rendered HTML")
    parser.add_argument("--comments", action="store_true", help="include every comment")
    parser.add_argument("--worklogs", action="store_true", help="include every worklog")
    parser.add_argument("--changelog", action="store_true", help="include the change history, one row per changed field")
    parser.add_argument("--links", action="store_true", help="include issue links (blocks, relates to, ...)")
    parser.add_argument("--attachments", action="store_true", help="include attachment metadata")
    parser.add_argument("--download-attachments", metavar="DIR", help="save attachment files under DIR/<issue key>/ (implies --attachments)")
    parser.add_argument("--incremental", metavar="STATE_FILE",
                        help="only export what changed since the last run, appending to --output (CSV or JSON Lines)")
    parser.add_argument("--manifest", action="store_true", help="write <output>.manifest.json describing the export (needs --output)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="log progress to stderr (-vv shows requests too)")
    parser.add_argument("--max-attachment-mb", type=float, help="skip downloading attachments larger than this")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token, **config.tuning())


def sidecar_path(output, name):
    """issues.csv -> issues-<name>.csv, and issues.csv.gz -> issues-<name>.csv.gz"""
    compressed = output.endswith(".gz")
    base = output[:-3] if compressed else output
    stem, dot, ext = base.rpartition(".")
    path = "{}-{}.{}".format(stem, name, ext) if dot else "{}-{}".format(base, name)
    return path + ".gz" if compressed else path


def build_extras(args):
    extras = []
    if args.comments:
        extras.append(Extra("comments", ("comment",), comments.COLUMNS,
                            lambda client, issue: comments.rows(issue["key"], comments.fetch(client, issue))))
    if args.worklogs:
        extras.append(Extra("worklogs", ("worklog",), worklogs.COLUMNS,
                            lambda client, issue: worklogs.rows(issue["key"], worklogs.fetch(client, issue))))
    if args.changelog:
        extras.append(Extra("changelog", (), changelog.COLUMNS,
                            lambda client, issue: changelog.rows(issue["key"], changelog.fetch(client, issue)), ("changelog",)))
    if args.links:
        extras.append(Extra("links", ("issuelinks",), links.COLUMNS,
                            lambda client, issue: links.rows(issue["key"], issue["fields"].get("issuelinks"))))
    if args.attachments or args.download_attachments:
        max_bytes = int(args.max_attachment_mb * 1024 * 1024) if args.max_attachment_mb else None

        def collect(client, issue):
            files = issue["fields"].get("attachment") or []
            notes = {}
            if args.download_attachments:
                notes = attachments.download_all(client, issue["key"], files, args.download_attachments, max_bytes)
            return attachments.rows(issue["key"], files, notes)
        extras.append(Extra("attachments", ("attachment",), attachments.COLUMNS, collect))
    return extras


def open_for_output(stack, path, appending, columns_format):
    """Open an output file; when appending to a non-empty file the CSV header must not be repeated."""
    header = not (appending and os.path.exists(path) and os.path.getsize(path) > 0)
    handle = stack.enter_context(writers.open_text(path, "a" if appending else "w"))
    return handle, header


def setup_logging(verbosity):
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(message)s", stream=sys.stderr)


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    try:
        args.jql = jqlbuild.build(args.jql, args.project, args.status, args.updated_since)
    except jqlbuild.JqlError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    extras = build_extras(args)
    nested = args.format in writers.NESTED
    if extras and not nested and not args.output:
        print("error: --{} needs --output when writing CSV".format(extras[0].name), file=sys.stderr)
        return 2
    if args.incremental and (not args.output or args.format == "json"):
        print("error: --incremental needs --output and CSV or JSON Lines (a JSON array cannot be appended to)", file=sys.stderr)
        return 2
    if args.manifest and not args.output:
        print("error: --manifest needs --output", file=sys.stderr)
        return 2
    try:
        client = client or make_client()
        started = manifest.now()
        custom = fieldmap.resolve(client, args.field)
        columns = flat_columns(custom, args.html)
        only = None
        if args.columns:
            only = tuple(c.strip() for c in args.columns.split(",") if c.strip())
            unknown = [c for c in only if c not in columns]
            if unknown:
                raise fieldmap.FieldError("unknown column(s): {} (choose from {})".format(", ".join(unknown), ", ".join(columns)))
            columns = only
        jql, tracker, appending, previous = args.jql, None, False, None
        if args.incremental:
            previous = incremental.load(args.incremental)
            if previous and previous["jql"] != args.jql:
                print("warning: the query changed since the last run; exporting everything again", file=sys.stderr)
                previous = None
            if previous and previous["last_updated"]:
                jql, appending = incremental.jql_since(args.jql, previous["last_updated"]), True
            tracker = previous or incremental.fresh(args.jql)
        with contextlib.ExitStack() as stack:
            if args.output:
                stream, header = open_for_output(stack, args.output, appending, args.format)
            else:
                stream, header = (out if out is not None else sys.stdout), True
            main_sink = writers.open_sink(args.format, stream, columns, header)
            side_sinks = {}
            if not nested:
                for extra in extras:
                    handle, side_header = open_for_output(stack, sidecar_path(args.output, extra.name), appending, "csv")
                    side_sinks[extra.name] = writers.open_sink("csv", handle, extra.columns, side_header)
            seen = []
            try:
                skip = (lambda issue: incremental.already_exported(tracker, issue)) if appending else None
                count = exporter.export(client, jql, main_sink, extras, side_sinks, nested, observe=seen.append, skip=skip, custom=custom, html=args.html, limit=args.limit, only=only)
            finally:
                main_sink.close()
        if args.incremental:
            incremental.save(args.incremental, incremental.advance(tracker, seen, count))
        if args.manifest:
            files = {args.output: count}
            files.update({sidecar_path(args.output, name): sink.count for name, sink in side_sinks.items()})
            manifest.write(args.output + ".manifest.json", manifest.build(args.jql, args.format, started, manifest.now(), files))
    except (config.ConfigError, incremental.StateError, fieldmap.FieldError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
