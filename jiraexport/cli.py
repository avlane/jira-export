"""Command line entry point: jira-export --jql ... --output issues.csv"""
import argparse
import sys

from . import comments, config, issues, worklogs, writers
from .client import JiraClient, JiraError
from .flatten import COLUMNS, flatten

# name -> (extra search fields, sidecar columns, collector)
EXTRAS = {
    "comments": (("comment",), comments.COLUMNS, lambda client, issue: comments.rows(issue["key"], comments.fetch(client, issue))),
    "worklogs": (("worklog",), worklogs.COLUMNS, lambda client, issue: worklogs.rows(issue["key"], worklogs.fetch(client, issue))),
}


def build_parser():
    parser = argparse.ArgumentParser(prog="jira-export", description="Export Jira Cloud issues selected by JQL.")
    parser.add_argument("--jql", required=True, help="JQL query selecting the issues")
    parser.add_argument("--output", "-o", help="file to write (default: standard output)")
    parser.add_argument("--format", "-f", choices=("csv", "json"), default="csv", help="output format (default csv)")
    parser.add_argument("--comments", action="store_true",
                        help="also write every comment to <output>-comments.csv (needs --output)")
    parser.add_argument("--worklogs", action="store_true",
                        help="also write every worklog to <output>-worklogs.csv (needs --output)")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def sidecar_path(output, name):
    stem, dot, ext = output.rpartition(".")
    return "{}-{}.{}".format(stem, name, ext) if dot else "{}-{}".format(output, name)


def main(argv=None, client=None, out=None):
    args = build_parser().parse_args(argv)
    selected = [name for name in EXTRAS if getattr(args, name)]
    if selected and not args.output:
        print("error: --{} needs --output".format(selected[0]), file=sys.stderr)
        return 2
    try:
        client = client or make_client()
        found = {name: [] for name in selected}
        fields = issues.DEFAULT_FIELDS + tuple(f for name in selected for f in EXTRAS[name][0])

        def rows_for():
            for issue in issues.search(client, args.jql, fields=fields):
                for name in selected:
                    found[name].extend(EXTRAS[name][2](client, issue))
                yield flatten(issue)

        write = writers.writer_for(args.format)
        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as handle:
                count = write(rows_for(), COLUMNS, handle)
            for name in selected:
                with open(sidecar_path(args.output, name), "w", newline="", encoding="utf-8") as handle:
                    writers.write_csv(found[name], EXTRAS[name][1], handle)
        else:
            count = write(rows_for(), COLUMNS, out if out is not None else sys.stdout)
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print("exported {} issues".format(count), file=sys.stderr)
    return 0
