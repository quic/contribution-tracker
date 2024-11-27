#
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#

import re
import sys
from collections import Counter

from . import iomanager

# A separator for `git log --format fields`
SEP = "§"  # not valid for email addresses
COMMON_LOG_OPTS = f"--no-merges --format='%ae{SEP}%ad' --date='format:%s'"

metric_registry = {}


def register_metric(func):
    metric_registry[func.__name__] = func
    return func


def secs_to_days(secs):
    return secs // 60 // 60 // 24


def bin_num(args, timestamp):
    timestamp = int(timestamp)
    num = secs_to_days(timestamp - args.initial_timestamp) // args.period
    if num < 0:
        num = 0
    elif num >= args.groups:
        num = args.groups - 1
    return num


cache_patches_to_org_files = {}


def patches_to_org_files(args, org):
    if org in cache_patches_to_org_files:
        return cache_patches_to_org_files[org]
    patches_by_org = [Counter() for _ in range(args.groups)]
    log = iomanager.gitlog(
        f"{COMMON_LOG_OPTS} {args.since} -- {iomanager.ORG_FILES[org]}"
    )
    for line in log:
        author, timestamp = line.split(SEP)
        patches_by_org[bin_num(args, timestamp)][iomanager.org_from_email(author)] += 1
    cache_patches_to_org_files[org] = patches_by_org
    return patches_by_org


@register_metric
def total_patches(args):
    total_patches = [Counter({org: 0 for org in args.orgs}) for _ in range(args.groups)]
    log = iomanager.gitlog(f"{COMMON_LOG_OPTS} {args.since}")
    for line in iomanager.bar("Counting total patches").iter(log):
        email, timestamp = line.split(SEP)
        org = iomanager.org_from_email(email)
        total_patches[bin_num(args, timestamp)][org] += 1
    return total_patches


@register_metric
def internal_patches_to_org_files(args):
    patches = [Counter() for _ in range(args.groups)]
    for org in iomanager.bar("Counting internal patches to organization files").iter(
        args.orgs
    ):
        patches_by_org = patches_to_org_files(args, org)
        for i in range(args.groups):
            patches[i][org] = patches_by_org[i][org]
    return patches


@register_metric
def external_patches_to_org_files(args):
    patches = [Counter() for _ in range(args.groups)]
    for org in iomanager.bar("Counting external patches to organization files").iter(
        args.orgs
    ):
        patches_by_org = patches_to_org_files(args, org)
        for i in range(args.groups):
            for other_orgs in patches_by_org[i].keys() - [org]:
                patches[i][org] += patches_by_org[i][other_orgs]
    return patches


def count_by_grep_criteria(args, regexfn, bar_info):
    results = [Counter() for _ in range(args.groups)]
    for org in iomanager.bar(bar_info).iter(args.orgs):
        log_args = f"{COMMON_LOG_OPTS} {args.since} --grep='{regexfn(org)}' -i -E"
        for line in iomanager.gitlog(log_args):
            email, timestamp = line.split(SEP)
            results[bin_num(args, timestamp)][org] += 1
    return results


@register_metric
def reviewed_patches(args):
    regexfn = (
        lambda org: f"(acked-by|tested-by|reviewed-by):.*{iomanager.org_email_regex(org)}"
    )
    bar_info = "Counting org-reviewed patches"
    return count_by_grep_criteria(args, regexfn, bar_info)


@register_metric
def reported_by_patches(args):
    regexfn = (
        lambda org: f"(reported-by|suggested-by):.*{iomanager.org_email_regex(org)}"
    )
    bar_info = "Counting org-reported patches"
    return count_by_grep_criteria(args, regexfn, bar_info)


def gather_stats(args):
    if any(metric not in metric_registry for metric in args.metrics):
        sys.exit(
            f"FATAL: unknown metric '{metric}'. "
            + "Known ones:\n"
            + "\n".join(iomanager.all_metrics)
        )

    total = len(args.metrics)
    results = [list() for _ in range(args.groups)]
    headers = []
    for i, metric in enumerate(args.metrics):
        metric_fn = metric_registry[metric]
        print(f"======= STEP {i} / {total}: {metric}")
        this_results = metric_fn(args)
        for i in range(args.groups):
            results[i].append(this_results[i])
        headers.append(metric)
        print()
    return results, headers
