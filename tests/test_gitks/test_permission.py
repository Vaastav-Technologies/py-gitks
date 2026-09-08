#!/usr/bin/env python3
# coding=utf-8

"""
tests for the request → approve / deny permission flow.

Uses the same ``repo_local`` (gitbolt) and worktree generator pattern as
``test_init.py``. GPG homes for generated keys are under pytest temp dirs,
except the owner secret key which is created in the repo's approved GPG home
after ``init()``.
"""

from pathlib import Path

import pytest

from gitks.core import (
    KeyReviewStatus,
    KeyUploadStatus,
)
from gitks.core.constants import (
    APPROVED_STR,
    DENIED_STR,
    GIT_KS_DIR,
    GIT_KS_KEYS_BASE_BRANCH,
    REQUESTS_STR,
)
from gitks.core.gpg import make_detached_signature
from gitks.core.impl import (
    BaseDirWorkTreeGenerator,
    WorkTreeGitKeyServerImpl,
    WorkTreeGenerator,
)

gnupg = pytest.importorskip("gnupg")


class _AcceptAllKeys:
    def validate_key(self, public_key: bytes | str) -> None:
        return None


@pytest.fixture
def worktree_for_test(tmp_path) -> WorkTreeGenerator:
    return BaseDirWorkTreeGenerator(Path(tmp_path, "keys-base"))


def _generate_keypair(home: Path, real_name: str, email: str):
    home.mkdir(parents=True, exist_ok=True)
    gpg = gnupg.GPG(gnupghome=str(home))
    params = gpg.gen_key_input(
        key_type="EDDSA",
        key_curve="Ed25519",
        name_real=real_name,
        name_email=email,
        no_protection=True,
        expire_date="0",
    )
    generated = gpg.gen_key(params)
    if not generated.fingerprint:
        params = gpg.gen_key_input(
            key_type="RSA",
            key_length=2048,
            name_real=real_name,
            name_email=email,
            no_protection=True,
            expire_date="0",
        )
        generated = gpg.gen_key(params)
    assert generated.fingerprint, f"gpg key generation failed: {generated.stderr}"
    public_key = gpg.export_keys(generated.fingerprint)
    assert public_key
    return generated.fingerprint.replace(" ", "").upper(), public_key


@pytest.fixture(scope="module")
def alice_keys(tmp_path_factory):
    home = tmp_path_factory.mktemp("perm-alice")
    fingerprint, public_key = _generate_keypair(
        home, "Alice Example", "alice@example.com"
    )
    return home, fingerprint, public_key


def _make_ks(repo_local, worktree_for_test) -> WorkTreeGitKeyServerImpl:
    return WorkTreeGitKeyServerImpl(
        _AcceptAllKeys(),
        repo_local,
        user_name="ss",
        user_email="ss@ss.ss",
        worktree_generator=worktree_for_test,
    )


def _init_ks(repo_local, worktree_for_test) -> WorkTreeGitKeyServerImpl:
    ks = _make_ks(repo_local, worktree_for_test)
    ks.init()
    return ks


def _install_owner_key(repo_local) -> None:
    owner_home = Path(repo_local, GIT_KS_DIR, APPROVED_STR)
    _generate_keypair(owner_home, "Repo Owner", "owner@example.com")


def _queue_key(ks: WorkTreeGitKeyServerImpl, alice_keys, signature: str | None = None):
    alice_home, fingerprint, public_key = alice_keys
    if signature is None:
        signature = make_detached_signature(public_key, alice_home)
    result = ks.send_key(public_key, signature=signature)
    return fingerprint, public_key, result


def _state_worktrees(ks: WorkTreeGitKeyServerImpl):
    base = GIT_KS_KEYS_BASE_BRANCH
    return (
        ks.worktree_dir_for(f"{base}/{REQUESTS_STR}"),
        ks.worktree_dir_for(f"{base}/{APPROVED_STR}"),
        ks.worktree_dir_for(f"{base}/{DENIED_STR}"),
    )


class TestSendKeyRequest:
    def test_send_returns_pending(self, repo_local, worktree_for_test, alice_keys):
        ks = _init_ks(repo_local, worktree_for_test)
        _fp, _pub, result = _queue_key(ks, alice_keys)
        assert result.status == KeyUploadStatus.PENDING
        assert result.server_id

    def test_send_lands_in_requests_not_approved(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        key_id, _pub, _result = _queue_key(ks, alice_keys)
        requests_wt, approved_wt, _denied_wt = _state_worktrees(ks)
        assert (requests_wt / f"{key_id}.asc").is_file()
        assert (requests_wt / f"{key_id}.asc.sig").is_file()
        assert not (approved_wt / f"{key_id}.asc").exists()

    def test_list_pending_sees_request(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        key_id, public_key, _result = _queue_key(ks, alice_keys)
        pending = ks.list_pending_keys()
        assert len(pending) == 1
        assert pending[0].key_id == key_id
        assert pending[0].public_key == public_key
        assert pending[0].requester_signature

    def test_duplicate_send_is_already_exists(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        _queue_key(ks, alice_keys)
        _fp, _pub, second = _queue_key(ks, alice_keys)
        assert second.status == KeyUploadStatus.ALREADY_EXISTS


class TestApproveKey:
    def test_approve_moves_request_to_approved(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        _install_owner_key(repo_local)
        key_id, _pub, _result = _queue_key(ks, alice_keys)
        review = ks.approve_key(key_id)
        assert review.status == KeyReviewStatus.APPROVED
        assert review.server_id
        requests_wt, approved_wt, _denied_wt = _state_worktrees(ks)
        assert not (requests_wt / f"{key_id}.asc").exists()
        assert (approved_wt / f"{key_id}.asc").is_file()
        assert (approved_wt / f"{key_id}.asc.sig").is_file()
        assert (approved_wt / f"{key_id}.owner.sig").is_file()
        assert ks.list_pending_keys() == []

    def test_approve_unknown_id(self, repo_local, worktree_for_test):
        ks = _init_ks(repo_local, worktree_for_test)
        review = ks.approve_key("NOTAKEY")
        assert review.status == KeyReviewStatus.NOT_FOUND

    def test_approve_bad_signature_stays_pending(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        _install_owner_key(repo_local)
        key_id, _pub, _result = _queue_key(ks, alice_keys, signature="not-a-signature")
        review = ks.approve_key(key_id)
        assert review.status == KeyReviewStatus.INVALID_SIGNATURE
        requests_wt, approved_wt, _denied_wt = _state_worktrees(ks)
        assert (requests_wt / f"{key_id}.asc").is_file()
        assert not (approved_wt / f"{key_id}.asc").exists()


class TestDenyKey:
    def test_deny_moves_request_to_denied(
        self, repo_local, worktree_for_test, alice_keys
    ):
        ks = _init_ks(repo_local, worktree_for_test)
        _install_owner_key(repo_local)
        key_id, _pub, _result = _queue_key(ks, alice_keys)
        reason = "uid does not match organisation policy"
        review = ks.deny_key(key_id, reason)
        assert review.status == KeyReviewStatus.DENIED
        assert review.reason == reason
        requests_wt, _approved_wt, denied_wt = _state_worktrees(ks)
        assert not (requests_wt / f"{key_id}.asc").exists()
        assert (denied_wt / f"{key_id}.asc").is_file()
        assert (denied_wt / f"{key_id}.asc.sig").is_file()
        assert (denied_wt / f"{key_id}.owner.sig").is_file()
        assert (denied_wt / f"{key_id}.reason.txt").read_text(
            encoding="utf-8"
        ) == reason
        assert ks.list_pending_keys() == []

    def test_deny_unknown_id(self, repo_local, worktree_for_test):
        ks = _init_ks(repo_local, worktree_for_test)
        review = ks.deny_key("NOTAKEY", "n/a")
        assert review.status == KeyReviewStatus.NOT_FOUND
