#
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#

import json
import datetime

JSON_VERSION = 1.0


def read(filename):
    with open(filename, "r") as f:
        return json.load(f)


def write(filename, json_obj):
    with open(filename, "w") as fp:
        json.dump(json_obj, fp, default=str, indent=4)
    print(f"saved {filename}")


def generate(args, results, headers):
    json_obj = {}
    initial = datetime.date.fromtimestamp(args.initial_timestamp)
    json_obj["version"] = JSON_VERSION
    json_obj["gen_time"] = datetime.date.today()
    json_obj["time_period_days"] = args.period
    json_obj["repo"] = args.repo
    json_obj["timestamps"] = [
        str(initial + datetime.timedelta(days=(args.period * i)))
        for i in range(args.groups)
    ]
    json_obj["metrics"] = headers
    json_obj["orgs"] = list(args.orgs)
    json_obj["data"] = {
        header: {
            time: {org: results[time_id][header_id][org] for org in args.orgs}
            for time_id, time in enumerate(json_obj["timestamps"])
        }
        for header_id, header in enumerate(headers)
    }

    return json_obj
