"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import contextlib
import os
import sys

from . import attachments, comments, config, exporter, incremental, worklogs, writers
from .client import JiraClient, JiraError
from .exporter import Extra
from .flatten import COLUMNS


def build_parser():
    parser = argparse.ArgumentParser(prog="jira-export", description="Export Jira Cloud issues selected by JQL.")
    parser.add_argument("--jql", required=True, help="JQL query selecting the issues")
    parser.add_argument("--output", "-o", help="file to write (default: standard output)")
    parser.add_argument("--format", "-f", choices=sorted(writers.SINKS), default="csv", help="output format (default csv)")
    parser.add_argument("--comments", action="store_true", help="include every comment")
    parser.add_argument("--worklogs", action="store_true", help="include every worklog")
    parser.add_argument("--attachments", action="store_true", help="include attachment metadata")
    parser.add_argument("--download-attachments", metavar="DIR", help="save attachment files under DIR/<issue key>/ (implies --attachments)")
    parser.add_argument("--incremental", metavar="STATE_FILE",
                        help="only export what changed since the last run, appending to --output (CSV or JSON Lines)")
    parser.add_argument("--max-attachment-mb", type=float, help="skip downloading attachments larger than this")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def sidecar_path(output, name):
    stem, dot, ext = output.rpartition(".")
    return "{}-{}.{}".format(stem, name, ext) if dot else "{}-{}".format(output, name)


def build_extras(args):
    extras = []
    if args.comments:
        extras.append(Extra("comments", ("comment",), comments.COLUMNS,
                            lambda client, issue: comments.rows(issue["key"], comments.fetch(client, issue))))
    if args.worklogs:
        extras.append(Extra("worklogs", ("worklog",), worklogs.COLUMNS,
                            lambda client, issue: worklogs.rows(issue["key"], worklogs.fetch(client, issue))))
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
    handle = stack.enter_context(open(path, "a" if appending else "w", newline="", encoding="utf-8"))
    return handle, header


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    extras = build_extras(args)
    nested = args.format in writers.NESTED
    if extras and not nested and not args.output:
        print("error: --{} needs --output when writing CSV".format(extras[0].name), file=sys.stderr)
        return 2
    if args.incremental and (not args.output or args.format == "json"):
        print("error: --incremental needs --output and CSV or JSON Lines (a JSON array cannot be appended to)", file=sys.stderr)
        return 2
    try:
        client = client or make_client()
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
            main_sink = writers.open_sink(args.format, stream, COLUMNS, header)
            side_sinks = {}
            if not nested:
                for extra in extras:
                    handle, side_header = open_for_output(stack, sidecar_path(args.output, extra.name), appending, "csv")
                    side_sinks[extra.name] = writers.open_sink("csv", handle, extra.columns, side_header)
            seen = []
            try:
                count = exporter.export(client, jql, main_sink, extras, side_sinks, nested, observe=seen.append)
            finally:
                main_sink.close()
        if args.incremental:
            incremental.save(args.incremental, incremental.advance(tracker, seen, count))
    except (config.ConfigError, incremental.StateError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
