#!/usr/bin/env python3
# coding=utf-8

"""
tests for the request → repo-owner approve/deny permission flow.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import gnupg
import pytest

from gitks.core.constants import (
    APPROVED_STR,
    DENIED_STR,
    DENIED_REASON_SUFFIX,
    GIT_KS_KEYS_BASE_BRANCH,
    KEY_SIG_SUFFIX,
    OWNER_SIG_SUFFIX,
    REQUESTS_STR,
)
from gitks.core.gpg import GpgKeyValidator, detached_sign, fingerprint_of
from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl
from gitks.core.model import KeyUploadStatus


def _gpg_or_skip() -> None:
    if not shutil.which("gpg"):
        pytest.skip("gpg is not available")


def _gen_key(gpg: gnupg.GPG, name: str, email: str):
    params = gpg.gen_key_input(
        name_real=name,
        name_email=email,
        key_type="RSA",
        key_length=2048,
        no_protection=True,
    )
    key = gpg.gen_key(params)
    assert key.fingerprint, f"failed to generate key for {email}"
    return key


@pytest.fixture
def gpg_home(tmp_path):
    _gpg_or_skip()
    home = tmp_path / "gnupg"
    home.mkdir()
    os.environ["GNUPGHOME"] = str(home)
    gpg = gnupg.GPG(gnupghome=str(home))
    requester = _gen_key(gpg, "Requester", "req@example.test")
    owner = _gen_key(gpg, "Repo Owner", "owner@example.test")
    yield gpg, requester, owner
    os.environ.pop("GNUPGHOME", None)


def _ks(repo_local, tmp_path):
    return WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        repo_local,
        user_name="ss",
        user_email="ss@ss.ss",
        worktree_generator=BaseDirWorkTreeGenerator(Path(tmp_path, "keys-base")),
    )


def _export_and_sign(gpg: gnupg.GPG, key) -> tuple[str, str, str]:
    public_key = gpg.export_keys(key.fingerprint)
    fingerprint = fingerprint_of(public_key)
    signature = detached_sign(
        public_key, fingerprint, os.environ["GNUPGHOME"]
    )
    return public_key, fingerprint, signature


def _stage_file(ks: WorkTreeGitKeyServerImpl, stage: str, name: str) -> Path:
    return ks._stage_worktree(stage) / name


def test_request_lands_on_requests_not_approved(repo_local, tmp_path, gpg_home):
    gpg, requester, _owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, fingerprint, signature = _export_and_sign(gpg, requester)

    result = ks.request_key(public_key, signature)

    assert result.status == KeyUploadStatus.PENDING
    assert _stage_file(ks, REQUESTS_STR, fingerprint).exists()
    assert _stage_file(ks, REQUESTS_STR, f"{fingerprint}{KEY_SIG_SUFFIX}").exists()
    assert not _stage_file(ks, APPROVED_STR, fingerprint).exists()
    pending = ks.list_pending_keys()
    assert [item.key_id for item in pending] == [fingerprint]


def test_duplicate_request_already_exists(repo_local, tmp_path, gpg_home):
    gpg, requester, _owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, _fingerprint, signature = _export_and_sign(gpg, requester)
    ks.request_key(public_key, signature)
    result = ks.request_key(public_key, signature)
    assert result.status == KeyUploadStatus.ALREADY_EXISTS


def test_approve_moves_to_approved(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, fingerprint, signature = _export_and_sign(gpg, requester)
    ks.request_key(public_key, signature)
    owner_fp = fingerprint_of(gpg.export_keys(owner.fingerprint))
    ks.register_approver(owner_fp)

    result = ks.approve_key(fingerprint, owner_fp)

    assert result.status == KeyUploadStatus.SUCCESS
    assert not _stage_file(ks, REQUESTS_STR, fingerprint).exists()
    assert _stage_file(ks, APPROVED_STR, fingerprint).exists()
    assert _stage_file(ks, APPROVED_STR, f"{fingerprint}{OWNER_SIG_SUFFIX}").exists()
    assert ks.list_pending_keys() == []
    received = ks.receive_key(fingerprint)
    assert fingerprint_of(received) == fingerprint


def test_bad_requester_signature_moves_to_denied(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, fingerprint, _signature = _export_and_sign(gpg, requester)
    other_sig = detached_sign("not-the-key", fingerprint, os.environ["GNUPGHOME"])
    # request_key itself rejects a bad signature; plant a pending request with a
    # mismatched sig so approve_key takes the denied path.
    ks.request_key(public_key, detached_sign(public_key, fingerprint, os.environ["GNUPGHOME"]))
    pending_sig = ks._stage_worktree(REQUESTS_STR) / f"{fingerprint}{KEY_SIG_SUFFIX}"
    pending_sig.write_text(other_sig, encoding="utf-8")
    owner_fp = fingerprint_of(gpg.export_keys(owner.fingerprint))
    ks.register_approver(owner_fp)

    result = ks.approve_key(fingerprint, owner_fp)

    assert result.status == KeyUploadStatus.DENIED
    assert _stage_file(ks, DENIED_STR, fingerprint).exists()
    assert _stage_file(ks, DENIED_STR, f"{fingerprint}{DENIED_REASON_SUFFIX}").read_text(
        encoding="utf-8"
    )
    assert not _stage_file(ks, APPROVED_STR, fingerprint).exists()


def test_unauthorized_owner_moves_to_denied(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, fingerprint, signature = _export_and_sign(gpg, requester)
    ks.request_key(public_key, signature)
    owner_fp = fingerprint_of(gpg.export_keys(owner.fingerprint))

    result = ks.approve_key(fingerprint, owner_fp)

    assert result.status == KeyUploadStatus.DENIED
    assert _stage_file(ks, DENIED_STR, fingerprint).exists()
    assert not _stage_file(ks, APPROVED_STR, fingerprint).exists()


def test_explicit_deny(repo_local, tmp_path, gpg_home):
    gpg, requester, owner = gpg_home
    ks = _ks(repo_local, tmp_path)
    ks.init()
    public_key, fingerprint, signature = _export_and_sign(gpg, requester)
    ks.request_key(public_key, signature)
    owner_fp = fingerprint_of(gpg.export_keys(owner.fingerprint))
    ks.register_approver(owner_fp)

    result = ks.deny_key(fingerprint, owner_fp, "policy")

    assert result.status == KeyUploadStatus.DENIED
    reason = _stage_file(ks, DENIED_STR, f"{fingerprint}{DENIED_REASON_SUFFIX}")
    assert reason.read_text(encoding="utf-8") == "policy"
    assert GIT_KS_KEYS_BASE_BRANCH in str(ks._keys_base_branch())
