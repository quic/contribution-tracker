#
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#

import testframework
from src import json_parser, iomanager, metrics
import random
import os
import yaml
import datetime

CONFIG_DATA = dict(
    org_files=dict(
        org1="foo",
        org2="dir",
    ),
    org_domains=dict(
        org1="xyz",
        org2="ghi",
    ),
)

today = datetime.date.today()
timestamp = str(today.replace(year=(today.year - 10)))

EXPECTED_JSON = {
    "gen_time": today,
    "metrics": [
        "total_patches",
        "reviewed_patches",
        "internal_patches_to_org_files",
        "external_patches_to_org_files",
        "reported_by_patches",
    ],
    "orgs": ["org1", "org2"],
    "repo": "repo",
    "time_period_days": 3650,
    "timestamps": [timestamp],
    "version": 1.0,
    "data": {
        "external_patches_to_org_files": {timestamp: {"org1": 1, "org2": 0}},
        "internal_patches_to_org_files": {timestamp: {"org1": 2, "org2": 0}},
        "reported_by_patches": {timestamp: {"org1": 0, "org2": 1}},
        "reviewed_patches": {timestamp: {"org1": 0, "org2": 1}},
        "total_patches": {timestamp: {"org1": 3, "org2": 1}},
    },
}


def commit(repo, email, path, message=None):
    path = f"{repo}/{path}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(random.randbytes(5))
    iomanager.git(f"add {path}", repo)
    if message is None:
        message = f"add '{path}'"
    iomanager.git(
        f"-c user.name=user -c user.email={email} commit -m '{message}'", repo
    )


def mkrepo(repo_dir):
    repo_dir.mkdir()
    repo = str(repo_dir)
    iomanager.git("init", repo)

    commit(repo, "john@xyz.com", "foo/bar/file")
    commit(repo, "john@xyz.com", "file2", message="Suggested-by: bob@ghi.com")
    commit(repo, "alice@abc.xyz.com", "foo/file3", message="Reviewed-by: bob@ghi.com")
    commit(repo, "bob@ghi.com", "foo/bar/two/file4")


def write_config(path):
    with open(path, "w") as f:
        yaml.dump(CONFIG_DATA, f, default_flow_style=False)


def run(repo, config):
    args = iomanager.parse_args(
        [
            "--repo",
            repo,
            "--config",
            config,
            "--format",
            "json",
            "--period",
            "0",
            "--since",
            "10",
        ]
    )
    results, headers = metrics.gather_stats(args)
    return json_parser.generate(args, results, headers)


def test_extract(tmp_path):
    repo = tmp_path / "repo"
    mkrepo(repo)
    repo_path = str(repo)

    config_path = str(tmp_path / "config.yaml")
    write_config(config_path)

    results = run(repo_path, config_path)
    assert results == EXPECTED_JSON
