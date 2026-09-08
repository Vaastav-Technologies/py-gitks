#!/usr/bin/env python3

"""Minimal shared fixtures for gitks tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitks.core.constants import GIT_KS_VALIDATOR_CONFIG_KEY


@pytest.fixture
def repo_local(tmp_path) -> Path:
    """Empty git repo with gitks validator configured (for impl construction)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "--local", GIT_KS_VALIDATOR_CONFIG_KEY, "gpg"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo
