#!/usr/bin/env python3

"""Repo-owner promotion (multiple owners, two owner branches)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gitks.core import GitKsExitingException
from gitks.core.constants import OWNERS_KEYS_BRANCH, OWNERS_PROMOTE_BRANCH
from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl
from gitks.core.model import KeyUploadStatus

FIRST_PUB = "first-owner-public-key"
SECOND_PUB = "second-owner-public-key"
FIRST_FP = "A" * 40
SECOND_FP = "B" * 40


class _NoopValidator:
    def validate_key(self, public_key):
        pass


def _fingerprint_of(public_key, *args, **kwargs):
    key = public_key.decode() if isinstance(public_key, bytes) else public_key
    return {FIRST_PUB: FIRST_FP, SECOND_PUB: SECOND_FP}[key]


def _ks(repo_local, tmp_path) -> WorkTreeGitKeyServerImpl:
    return WorkTreeGitKeyServerImpl(
        _NoopValidator(),
        repo_local,
        user_name="ss",
        user_email="ss@ss.ss",
        worktree_generator=BaseDirWorkTreeGenerator(Path(tmp_path, "keys-base")),
    )


@patch.object(
    WorkTreeGitKeyServerImpl, "_verify_requester_detached_data", return_value=True
)
@patch("gitks.core.impl.fingerprint_of", side_effect=_fingerprint_of)
def test_first_and_second_repo_owner(mock_fp, mock_verify, repo_local, tmp_path):
    ks = _ks(repo_local, tmp_path)
    ks.init()
    result = ks.promote_repo_owner(FIRST_PUB, "first-sig")
    assert result.status == KeyUploadStatus.SUCCESS
    assert FIRST_FP in ks.list_repo_owners()

    result2 = ks.promote_repo_owner(
        SECOND_PUB,
        "second-sig",
        sponsor_public_key=FIRST_PUB,
        sponsor_signature="sponsor-sig",
    )
    assert result2.status == KeyUploadStatus.SUCCESS
    owners = ks.list_repo_owners()
    assert FIRST_FP in owners and SECOND_FP in owners
    keys_wt = ks.get_or_create_worktree(OWNERS_KEYS_BRANCH)
    promote_wt = ks.get_or_create_worktree(OWNERS_PROMOTE_BRANCH)
    assert (keys_wt / FIRST_FP).exists()
    assert (keys_wt / SECOND_FP).exists()
    assert (promote_wt / f"{SECOND_FP}.msg").exists()


@patch.object(
    WorkTreeGitKeyServerImpl, "_verify_requester_detached_data", return_value=True
)
@patch("gitks.core.impl.fingerprint_of", side_effect=_fingerprint_of)
def test_second_owner_without_sponsor_fails(mock_fp, mock_verify, repo_local, tmp_path):
    ks = _ks(repo_local, tmp_path)
    ks.init()
    ks.promote_repo_owner(FIRST_PUB, "first-sig")
    with pytest.raises(GitKsExitingException, match="sponsored"):
        ks.promote_repo_owner(SECOND_PUB, "second-sig")
