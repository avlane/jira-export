"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import sys

from . import config, issues, writers
from .client import JiraClient, JiraError
from .flatten import COLUMNS, flatten


def build_parser():
    parser = argparse.ArgumentParser(prog="jira-export", description="Export Jira Cloud issues selected by JQL.")
    parser.add_argument("--jql", required=True, help="JQL query selecting the issues")
    parser.add_argument("--output", "-o", help="file to write (default: standard output)")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    try:
        client = client or make_client()
        rows = (flatten(i) for i in issues.search(client, args.jql))
        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as handle:
                count = writers.write_csv(rows, COLUMNS, handle)
        else:
            count = writers.write_csv(rows, COLUMNS, out if out is not None else sys.stdout)
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
