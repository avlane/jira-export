"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import sys

from . import comments, config, issues, writers
from .client import JiraClient, JiraError
from .flatten import COLUMNS, flatten


def build_parser():
    parser = argparse.ArgumentParser(prog="jira-export", description="Export Jira Cloud issues selected by JQL.")
    parser.add_argument("--jql", required=True, help="JQL query selecting the issues")
    parser.add_argument("--output", "-o", help="file to write (default: standard output)")
    parser.add_argument("--comments", action="store_true",
                        help="also write every comment to <output>-comments.csv (needs --output)")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def sidecar_path(output, name):
    stem, dot, ext = output.rpartition(".")
    return "{}-{}.{}".format(stem, name, ext) if dot else "{}-{}".format(output, name)


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    if args.comments and not args.output:
        print("error: --comments needs --output", file=sys.stderr)
        return 2
    try:
        client = client or make_client()
        found = []

        def rows_for():
            for issue in issues.search(client, args.jql, fields=issues.DEFAULT_FIELDS + (("comment",) if args.comments else ())):
                if args.comments:
                    found.extend(comments.rows(issue["key"], comments.fetch(client, issue)))
                yield flatten(issue)

        rows = rows_for()
        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as handle:
                count = writers.write_csv(rows, COLUMNS, handle)
            if args.comments:
                with open(sidecar_path(args.output, "comments"), "w", newline="", encoding="utf-8") as handle:
                    writers.write_csv(found, comments.COLUMNS, handle)
        else:
            count = writers.write_csv(rows, COLUMNS, out if out is not None else sys.stdout)
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
