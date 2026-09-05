#!/usr/bin/env python3

"""Shared fixtures for gitks tests."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import gnupg
import pytest

from gitks.core.gpg import GpgKeyValidator, detached_sign, fingerprint_of
from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl


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
    """Isolated GPG home for tests. Not the user's live gnupg keyring."""
    _gpg_or_skip()
    home = Path(os.environ["APPDATA"]) / "gitks-pytest-gnupg" / tmp_path.name
    home.mkdir(parents=True, exist_ok=True)
    (home / "gpg.conf").write_text(
        "pinentry-mode loopback\nbatch\nno-tty\n", encoding="utf-8"
    )
    (home / "gpg-agent.conf").write_text("allow-loopback-pinentry\n", encoding="utf-8")
    prev = os.environ.get("GNUPGHOME")
    os.environ["GNUPGHOME"] = str(home)
    gpg = gnupg.GPG(gnupghome=str(home))
    requester = _gen_key(gpg, "Requester", "req@example.test")
    owner = _gen_key(gpg, "Repo Owner", "owner@example.test")
    yield gpg, requester, owner
    if prev is None:
        os.environ.pop("GNUPGHOME", None)
    else:
        os.environ["GNUPGHOME"] = prev
    shutil.rmtree(home, ignore_errors=True)


def ks_for_test(repo_local, tmp_path) -> WorkTreeGitKeyServerImpl:
    return WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        repo_local,
        user_name="ss",
        user_email="ss@ss.ss",
        worktree_generator=BaseDirWorkTreeGenerator(Path(tmp_path, "keys-base")),
    )


def export_and_sign(gpg: gnupg.GPG, key) -> tuple[str, str, str]:
    public_key = gpg.export_keys(key.fingerprint)
    fingerprint = fingerprint_of(public_key)
    signature = detached_sign(public_key, fingerprint, os.environ["GNUPGHOME"])
    return public_key, fingerprint, signature
