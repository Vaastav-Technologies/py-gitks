#!/usr/bin/env python3
# coding=utf-8

"""
Constants related to keyserver workings for ``gitks``.
"""
from pathlib import Path

from gitbolt import GIT_DIR

GIT_KS_BRANCH_ROOT = 'gitks-internal'
GIT_KS_KEYS_STR = 'keys'
GIT_KS_KEYS_BRANCH = '/'.join([GIT_KS_BRANCH_ROOT, GIT_KS_KEYS_STR])


REPO_GPG_HOME_STR = '.gpg-home'
REPO_GPG_HOME = Path(GIT_DIR, REPO_GPG_HOME_STR)
"""
GPG home directory for further usage.
"""

GIT_KS_DIR_STR = '.gitks'
GIT_KS_DIR = Path(REPO_GPG_HOME, GIT_KS_DIR_STR)
"""
Directory specific to gitks
"""

TEST_STR = '.test'
"""
Keys will be stored in this home directory before finalising.
"""

FINAL_STR = '.final'
"""
Finalised keys will be stored in this home directory.
"""
