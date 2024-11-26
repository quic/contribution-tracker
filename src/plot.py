#
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#

import sys
import matplotlib.pyplot as plt
import datetime

from itertools import accumulate

BASE_FONTSIZE = 16


def mkagg(arr):
    return [*accumulate(arr)]


def init_fig():
    plt.clf()
    plt.figure(figsize=(16, 9))
    plt.rcParams.update({"font.size": BASE_FONTSIZE})


def timeframe_str(obj):
    times = list(map(datetime.date.fromisoformat, obj["timestamps"]))
    start_year = times[0].year
    last_year = (times[-1] + datetime.timedelta(days=obj["time_period_days"])).year
    if start_year == last_year:
        timeframe = str(start_year)
    else:
        timeframe = f"[{start_year}, {last_year}]"
    return timeframe


def save(filename):
    plt.tight_layout()
    plt.savefig(filename, format="png")
    print(f"saved '{filename}'")


def review_index(reviewed_patches, submitted_patches):
    total = reviewed_patches + submitted_patches
    if total == 0:
        return 0
    return reviewed_patches / total


def mk_review_index_plot(args, obj):
    if (
        "reviewed_patches" not in obj["metrics"]
        or "total_patches" not in obj["metrics"]
    ):
        print("Skipping review-index plot")
        return

    init_fig()
    total_orgs = len(obj["orgs"])
    xaxis = range(total_orgs)

    reviewed_patches = obj["data"]["reviewed_patches"]
    total_patches = obj["data"]["total_patches"]

    yaxis = [
        review_index(
            sum(reviewed_patches[time][org] for time in obj["timestamps"]),
            sum(total_patches[time][org] for time in obj["timestamps"]),
        )
        for org in obj["orgs"]
    ]

    data = sorted(zip(yaxis, obj["orgs"]), key=lambda t: t[0])
    yaxis = [t[0] for t in data]
    orgs = [t[1] for t in data]
    colors = ["#325ea8" if o not in args.highlight else "#a88c32" for o in orgs]

    plt.hlines(y=0.5, xmin=-1, xmax=total_orgs, colors="red", lw=4, linestyles="--")
    plt.bar(xaxis, yaxis, color=colors)
    plt.xticks(xaxis, orgs, fontsize=BASE_FONTSIZE, rotation=60)
    ax = plt.gca()
    ax.set_ylim([0, 1])

    timeframe = timeframe_str(obj)
    plt.title(
        f"Ratio of reviews over total patches: {obj['repo']} repo {timeframe}",
        fontsize=BASE_FONTSIZE * 1.2,
    )
    save(f"{args.dir}/review_ratio_{obj['repo']}.png")


def mk_derived_plots(args, obj):
    mk_review_index_plot(args, obj)


def ordinal(num):
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")

    return f"{num:2}{suffix}"


def get_std_xaxis(obj):
    xaxis = []
    for date in map(datetime.date.fromisoformat, obj["timestamps"]):
        end_date = date + datetime.timedelta(days=obj["time_period_days"])
        date, end_date = str(date), str(end_date)
        if date[:4] != end_date[:4]:
            x = f"{date[:4]} - {end_date[:4]}"
        elif date[5:7] != end_date[5:7]:
            x = f"{date[:7]} - {end_date[:7]}"
        else:
            x = f"{date} - {end_date}"
        xaxis.append(x)
    return xaxis


def mkplots(args, obj, pretty_headers):
    xaxis = get_std_xaxis(obj)
    timeframe = timeframe_str(obj)

    if (
        "internal_patches_to_org_files" not in obj["metrics"]
        or "total_patches" not in obj["metrics"]
    ):
        print("Skipping 'org patches to non org files' plot")
    else:
        header = "internal_patches_to_non_org_files"
        pretty_header = "Patches to non-org files"
        obj["metrics"].append(header)
        pretty_headers.append(pretty_header)

        total_patches = obj["data"]["total_patches"]
        internal_patches_to_org_files = obj["data"]["internal_patches_to_org_files"]

        obj["data"][header] = {
            time: {
                org: (
                    total_patches[time][org] - internal_patches_to_org_files[time][org]
                )
                for org in obj["orgs"]
            }
            for time in obj["timestamps"]
        }

    for header_id, header in enumerate(obj["metrics"]):
        init_fig()
        current_y_values = []
        for y_id, org in enumerate(obj["orgs"]):
            yaxis = [obj["data"][header][time][org] for time in obj["timestamps"]]
            yaxis = mkagg(yaxis)
            current_y_values.append((yaxis[-1], y_id, org))
            if org in args.highlight:
                plt.plot(
                    xaxis,
                    yaxis,
                    "-o",
                    color="orange",
                    linewidth=14,
                    alpha=0.4,
                    label=org,
                )
            else:
                plt.plot(xaxis, yaxis, "-o", label=org)

        plt.title(
            f"{pretty_headers[header_id]}: {obj['repo']} repo {timeframe}",
            fontsize=BASE_FONTSIZE * 1.2,
        )
        plt.xlabel("Time")
        plt.ylabel("Accumulated number of patches")
        plt.xticks(fontsize=BASE_FONTSIZE * 0.8)

        current_y_values = sorted(current_y_values, key=lambda e: e[0], reverse=True)
        order = [e[1] for e in current_y_values]

        # Order the legend by latest size
        handles, labels = plt.gca().get_legend_handles_labels()
        plt.legend(
            [handles[i] for i in order],
            [f"{ordinal(pos+1)} {labels[i]}" for pos, i in enumerate(order)],
            fontsize=BASE_FONTSIZE,
            loc="upper left",
        )

        # Annotate lines
        # for i, element in enumerate(current_y_values):
        #    plt.text(10.2, i, element[2], horizontalalignment='left', color='black')

        save(f"{args.dir}/{header}_{obj['repo']}.png")

    mk_derived_plots(args, obj)
