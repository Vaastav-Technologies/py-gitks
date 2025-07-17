#!/usr/bin/env python3
# coding=utf-8

"""
Constants related to keyserver workings for ``gitks``.
"""

from pathlib import Path
from typing import Final

from gitbolt import GIT_DIR

from gitks.core.model import GitSelf

GIT_KS_STR = "gitks"
GIT_KS_BRANCH_ROOT = f"__{GIT_KS_STR}_internal"
GIT_KS_KEYS_STR = "keys"
GIT_KS_KEYS_BASE_BRANCH = "/".join([GIT_KS_BRANCH_ROOT, GIT_KS_KEYS_STR])
"""
Base branch for ``gitks`` to store keys.
"""


REPO_GPG_HOME_STR = ".gpg-home"
REPO_GPG_HOME = Path(GIT_DIR, REPO_GPG_HOME_STR)
"""
GPG home directory for further usage.
"""

GIT_KS_DIR_STR = f".{GIT_KS_STR}"
GIT_KS_DIR = Path(REPO_GPG_HOME, GIT_KS_DIR_STR)
"""
Directory specific to gitks
"""

TEST_STR = "test"
"""
Keys will be stored in this home directory and branch before finalising.
"""

FINAL_STR = "final"
"""
Finalised keys will be stored in this home directory and branch.
"""

BRANCH_STR = "branch"
DIR_STR = "dir"

GIT_KS_KEYS_CONFIG_KEY = ".".join([GIT_KS_STR, GIT_KS_KEYS_STR])
GIT_KS_BRANCH_CONFIG_KEY = ".".join([GIT_KS_KEYS_CONFIG_KEY, BRANCH_STR])
GIT_KS_DIR_CONFIG_KEY = ".".join([GIT_KS_KEYS_CONFIG_KEY, DIR_STR])

ENC_STR = "enc"
KEYSERVER_STR = "keyserver"
CONF_STR = "conf"
KEYSERVER_CONFIG_KEY = f"enc.{KEYSERVER_STR}"
KEYSERVER_BRANCH_NAME = f"__{ENC_STR}_internal/{KEYSERVER_STR}/{CONF_STR}"
REPO_CONF_BRANCH = "__enc_internal/conf/main"
"""
This branch stores all the repo configurations.
"""

SELF_REPO: Final[GitSelf] = GitSelf("__SELF_REPO__")
