"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import contextlib
import sys

from . import attachments, comments, config, exporter, worklogs, writers
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


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    extras = build_extras(args)
    nested = args.format in writers.NESTED
    if extras and not nested and not args.output:
        print("error: --{} needs --output when writing CSV".format(extras[0].name), file=sys.stderr)
        return 2
    try:
        client = client or make_client()
        with contextlib.ExitStack() as stack:
            if args.output:
                stream = stack.enter_context(open(args.output, "w", newline="", encoding="utf-8"))
            else:
                stream = out if out is not None else sys.stdout
            main_sink = writers.open_sink(args.format, stream, COLUMNS)
            side_sinks = {}
            if not nested:
                for extra in extras:
                    handle = stack.enter_context(open(sidecar_path(args.output, extra.name), "w", newline="", encoding="utf-8"))
                    side_sinks[extra.name] = writers.open_sink("csv", handle, extra.columns)
            try:
                count = exporter.export(client, args.jql, main_sink, extras, side_sinks, nested)
            finally:
                main_sink.close()
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
