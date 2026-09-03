#!/usr/bin/env python3
# coding=utf-8

"""Repo-owner promotion (multiple owners, two owner branches)."""

import os

import pytest

from gitks.core import GitKsExitingException
from gitks.core.constants import (
    OWNERS_KEYS_BRANCH,
    OWNERS_PROMOTE_BRANCH,
    owner_promote_message,
)
from gitks.core.gpg import detached_sign
from gitks.core.model import KeyUploadStatus
from tests.test_gitks.conftest import export_and_sign, ks_for_test


def test_first_and_second_repo_owner(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = ks_for_test(repo_local, tmp_path)
    ks.init()
    first_pub, first_fp, _ = export_and_sign(gpg, owner)
    msg = owner_promote_message(first_fp)
    first_sig = detached_sign(msg, first_fp, os.environ["GNUPGHOME"])
    result = ks.promote_repo_owner(first_pub, first_sig)
    assert result.status == KeyUploadStatus.SUCCESS
    assert first_fp in ks.list_repo_owners()

    second_pub, second_fp, _ = export_and_sign(gpg, requester)
    second_msg = owner_promote_message(second_fp)
    self_sig = detached_sign(second_msg, second_fp, os.environ["GNUPGHOME"])
    sponsor_sig = detached_sign(second_msg, first_fp, os.environ["GNUPGHOME"])
    result2 = ks.promote_repo_owner(
        second_pub,
        self_sig,
        sponsor_public_key=first_pub,
        sponsor_signature=sponsor_sig,
    )
    assert result2.status == KeyUploadStatus.SUCCESS
    owners = ks.list_repo_owners()
    assert first_fp in owners and second_fp in owners

    keys_wt = ks.get_or_create_worktree(OWNERS_KEYS_BRANCH)
    promote_wt = ks.get_or_create_worktree(OWNERS_PROMOTE_BRANCH)
    assert (keys_wt / first_fp).exists()
    assert (keys_wt / second_fp).exists()
    assert (promote_wt / f"{second_fp}.msg").exists()


def test_second_owner_without_sponsor_fails(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = ks_for_test(repo_local, tmp_path)
    ks.init()
    first_pub, first_fp, _ = export_and_sign(gpg, owner)
    msg = owner_promote_message(first_fp)
    ks.promote_repo_owner(
        first_pub, detached_sign(msg, first_fp, os.environ["GNUPGHOME"])
    )
    second_pub, second_fp, _ = export_and_sign(gpg, requester)
    second_msg = owner_promote_message(second_fp)
    self_sig = detached_sign(second_msg, second_fp, os.environ["GNUPGHOME"])
    with pytest.raises(GitKsExitingException, match="sponsored"):
        ks.promote_repo_owner(second_pub, self_sig)
