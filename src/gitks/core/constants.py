#!/usr/bin/env python3

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
GIT_KS_KEYS_BASE_BRANCH = f"{GIT_KS_BRANCH_ROOT}/{GIT_KS_KEYS_STR}"
"""
Base branch for ``gitks`` to store keys.
"""


REPO_GPG_HOME_STR = ".gpg-home"
REPO_GPG_HOME = Path(GIT_DIR, REPO_GPG_HOME_STR)
"""
Layout path under ``.git`` (not a keyring). Do not import OpenPGP keys here.
"""

GIT_KS_DIR_STR = f".{GIT_KS_STR}"
GIT_KS_DIR = Path(REPO_GPG_HOME, GIT_KS_DIR_STR)
"""
Directory specific to gitks. Not a GNUPGHOME and not used to import keys.
"""

GITKS_WORKTREES_DIR_STR = ".gitks-worktrees"
"""
Directory name for gitks worktrees (sibling of the repo parent).
"""

REQUESTS_STR = "requests"
"""
Pending key inclusion requests (public key + requester detached signature).
"""

APPROVED_STR = "approved"
"""
Repo-owner approved keys. Getters search this branch.
"""

DENIED_STR = "denied"
"""
Rejected key requests, with owner signature and rejection reason.
"""

KEY_STAGE_STRS = (REQUESTS_STR, APPROVED_STR, DENIED_STR)

# Backward-compatible aliases (old test/final layout).
TEST_STR = REQUESTS_STR
FINAL_STR = APPROVED_STR

URL_STR = "url"
CAPS_URL_STR = URL_STR.upper()
BRANCH_STR = "branch"
CAPS_BRANCH_STR = BRANCH_STR.upper()
DIR_STR = "dir"

GIT_KS_KEYS_CONFIG_KEY = f"{GIT_KS_STR}.{GIT_KS_KEYS_STR}"
GIT_KS_BRANCH_CONFIG_KEY = f"{GIT_KS_KEYS_CONFIG_KEY}.{BRANCH_STR}"
GIT_KS_DIR_CONFIG_KEY = f"{GIT_KS_KEYS_CONFIG_KEY}.{DIR_STR}"

ENC_STR = "enc"
KEYSERVER_STR = "keyserver"
CAPS_KEYSERVER_STR = KEYSERVER_STR.upper()
KEYSERVER_URL_F_NAME = f"{CAPS_KEYSERVER_STR}.{CAPS_URL_STR}"
KEYSERVER_BRANCH_F_NAME = f"{CAPS_KEYSERVER_STR}.{CAPS_BRANCH_STR}"
APPROVERS_STR = "APPROVERS"
KEYSERVER_APPROVERS_F_NAME = f"{CAPS_KEYSERVER_STR}.{APPROVERS_STR}"
"""
One repo-owner GPG fingerprint per line on the conf branch.
"""
KEY_SIG_SUFFIX = ".sig"
OWNER_SIG_SUFFIX = ".owner.sig"
COMMIT_SIG_SUFFIX = ".commit.sig"
DENIED_REASON_SUFFIX = ".reason"
CONF_STR = "conf"
GIT_KS_KEYSERVER_PATH_KEY = f"{GIT_KS_STR}.{KEYSERVER_STR}.path"
KEYSERVER_BRANCH_NAME = f"__{ENC_STR}_internal/{KEYSERVER_STR}/{CONF_STR}"
REPO_CONF_BRANCH = "__enc_internal/conf/main"
"""
This branch stores all the repo configurations.
"""

SELF_REPO: Final[GitSelf] = GitSelf("__SELF_REPO__")

OWNERS_STR = "owners"
GIT_KS_OWNERS_BASE_BRANCH = f"{GIT_KS_BRANCH_ROOT}/{OWNERS_STR}"
OWNERS_KEYS_STR = "keys"
OWNERS_PROMOTE_STR = "promote"
OWNERS_KEYS_BRANCH = f"{GIT_KS_OWNERS_BASE_BRANCH}/{OWNERS_KEYS_STR}"
"""
All repo-owner public keys (multiple owners for redundancy).
"""
OWNERS_PROMOTE_BRANCH = f"{GIT_KS_OWNERS_BASE_BRANCH}/{OWNERS_PROMOTE_STR}"
"""
Signed promotion messages for repo-owner keys.
"""
OWNER_PROMOTE_MESSAGE_PREFIX = "GITKS-PROMOTE-REPO-OWNER:"


def owner_promote_message(fingerprint: str) -> str:
    """Canonical message a key must sign to be promoted as a repo owner."""
    fp = fingerprint.replace(" ", "").upper()
    return f"{OWNER_PROMOTE_MESSAGE_PREFIX}{fp}\n"
