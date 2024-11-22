#
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#

import sys
from progress.bar import Bar
from termcolor import colored
from tabulate import tabulate
import yaml
import subprocess
import argparse
import os
import datetime
import re

from . import plot, json_parser

REPO_PATH = ""
BRANCH = ""
VERBOSE = False
ORG_FILES = {}
ORG_DOMAINS = {}
KNOWN_ORGS_REGEX = None


def warn(msg):
    if VERBOSE:
        print(colored(f" [WARN] {msg}", "yellow"))


def bar(info):
    return Bar(
        info,
        suffix="%(percent).1f%% (%(index).d / %(max).d) [%(elapsed_td)s / %(eta_td)s]",
    )


def run(cmd, env=None):
    if VERBOSE:
        print(colored(f' [INFO] Running "{cmd}" with env "{env}"', "blue"))
    out = subprocess.check_output(cmd, shell=True, text=True, env=env).strip()
    if out == "":
        return []
    return out.split("\n")


def git(cmd):
    git_env = {
        "HOME": "",
        "XDG_CONFIG_HOME": "",
        "GIT_CONFIG_NOGLOBAL": "1",
    }
    return run(f"git -C {REPO_PATH} {cmd}", env=git_env)


def gitlog(args):
    return git(f"log {BRANCH} {args}")


def load_config(args):
    global ORG_FILES
    global ORG_DOMAINS
    global KNOWN_ORGS_REGEX
    if args.config is None:
        if args.from_json is None:
            sys.exit("missing required --config file")
        return []
    with open(args.config) as f:
        data = yaml.safe_load(f)
        ORG_FILES = data["org_files"]
        ORG_DOMAINS = data["org_domains"]

        for k, v in ORG_FILES.items():
            ORG_FILES[k] = " ".join([f"'*{p}*'" for p in v.split()])

        known_orgs = ORG_FILES.keys()
        if args.orgs is None or len(args.orgs) == 0:
            args.orgs = known_orgs
        else:
            for org in args.orgs:
                if org not in known_orgs:
                    sys.exit(f"unknown org '{org}'")

        orgs = [
            c if c not in ORG_DOMAINS else ORG_DOMAINS[c].replace(" ", "|")
            for c in args.orgs
        ]
        KNOWN_ORGS_REGEX = re.compile(f".*({'|'.join(orgs)})[.].*")
        if "highlight" in data:
            return data["highlight"]
    return []


def org_email_regex(org):
    if org in ORG_DOMAINS:
        org = ORG_DOMAINS[org].replace(" ", "|")
    return f"@(.*[.]|)({org})[.]"


def org_from_email(email):
    domain = email.split("@")[-1]
    found = KNOWN_ORGS_REGEX.match(domain)
    if found is not None:
        org = found.group(1)
        if org in ORG_FILES:
            return org
        for org_id, aliases in ORG_DOMAINS.items():
            if org in aliases:
                return org_id
    return None  # Unknown org


def output_results(args, obj):
    if args.format == "plot":
        pretty_names = [
            metrics_pretty_names[all_metrics.index(h)] for h in obj["metrics"]
        ]
        plot.mkplots(args, obj, pretty_names)
    elif args.format == "json":
        json_parser.write(f"{args.dir}/{args.repo}.json", obj)
    else:
        for time_id, time in enumerate(obj["timestamps"]):
            print(f"========= TIMEFRAME {time_id}")
            table = [
                [obj["data"][header][time][c] for header in obj["metrics"]]
                for c in obj["orgs"]
            ]
            print(
                tabulate(
                    table,
                    headers=obj["metrics"],
                    showindex=obj["orgs"],
                    tablefmt="simple",
                )
            )


all_metrics = (
    "total_patches",
    "reviewed_patches",
    "internal_patches_to_org_files",
    "external_patches_to_org_files",
    "reported_by_patches",
)

metrics_pretty_names = (
    "Merged patches",
    "Reviewed patches",
    "Patches to org files from members",
    "Patches to org files from non-members",
    "Patches suggested by members",
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--since", default="10", help="Since when to count patches (in years)"
    )
    parser.add_argument(
        "-o", "--orgs", nargs="+", metavar="ORG", help="Limit to these organizations"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show infos and warnings"
    )
    parser.add_argument(
        "-f", "--format", default="cli", help="Output format: cli, json, plot."
    )
    parser.add_argument(
        "-d",
        "--dir",
        help="Directory to save plots when '--format plot' is used. Default is 'results'",
        default="results",
    )
    parser.add_argument(
        "-p",
        "--period",
        help="Group the data by this period (in days). Default is '730' (2 years)."
        + "You can also use 0 to use a single group.",
        default=730,
    )
    parser.add_argument(
        "-m",
        "--metrics",
        metavar="METRIC",
        nargs="+",
        default=all_metrics,
        help="Which metrics to gather (use ^ to exclude a metric). Default to all:\n"
        + "\n".join(all_metrics),
    )
    parser.add_argument(
        "-i",
        "--highlight",
        nargs="+",
        metavar="ORG",
        help="Highlight these organizations. Only meaningfull with --format plot.",
    )
    parser.add_argument(
        "-b",
        "--branch",
        default="HEAD",
        help="git branch to be analized. Default to HEAD",
    )
    parser.add_argument(
        "-r", "--repo", help="path to the git repo to be analized. Default to $PWD"
    )
    parser.add_argument(
        "-j",
        "--from-json",
        help="Load from json file instead of collecting data from a repo.",
    )
    parser.add_argument("--config", help="Config file to use.")
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    global REPO_PATH
    if args.repo is None:
        args.repo = os.getcwd()
    REPO_PATH = args.repo
    args.repo = os.path.basename(args.repo)

    global BRANCH
    BRANCH = args.branch

    no_metrics = list(filter(lambda e: e.startswith("^"), args.metrics))
    args.metrics = list(filter(lambda e: not e.startswith("^"), args.metrics))
    if args.metrics == []:
        args.metrics = all_metrics
    args.metrics = list(filter(lambda e: f"^{e}" not in no_metrics, args.metrics))

    if args.format not in ("plot", "json", "cli"):
        sys.exit("unknown --format")

    if args.format in ("plot", "json"):
        if not os.path.isdir(args.dir):
            try:
                os.mkdir(args.dir)
            except Exception as e:
                sys.exit(
                    f"--format {args.format}: failed to create out dir '{args.dir}': {e}"
                )

    config_highlight = load_config(args)
    if args.highlight is None:
        args.highlight = []
    args.highlight += config_highlight
    for org in args.highlight:
        if org not in args.orgs:
            sys.exit(f"invalid --highlight option: '{org}' is not in --orgs")

    timeframe_years = int(args.since)
    timeframe_days = timeframe_years * 365
    args.since = f"--since={args.since}.years.ago"

    args.period = int(args.period)
    if args.period == 0:
        args.period = timeframe_days

    # Push derivative args for convenience
    args.__dict__["groups"] = timeframe_days // args.period
    today = datetime.date.today()
    initial = int(today.replace(year=(today.year - timeframe_years)).strftime("%s"))
    args.__dict__["initial_timestamp"] = initial
    args.__dict__["timeframe_years"] = timeframe_years

    return args
