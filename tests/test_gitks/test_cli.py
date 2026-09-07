#!/usr/bin/env python3

"""CLI argparse for gitks."""

from pathlib import Path

import pytest

from gitks.cli.__main__ import build_parser, cmd_clone, cmd_init
from gitks.core.constants import GIT_KS_DIR, GIT_KS_KEYS_BASE_BRANCH
from gitks.core.model import GitKSCloneResult


def test_cli_help_lists_init_and_clone():
    text = build_parser().format_help()
    assert "init" in text
    assert "clone" in text


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_cli_init_args():
    ns = build_parser().parse_args(
        [
            "init",
            "--dir",
            "repo",
            "--user-name",
            "cli",
            "--user-email",
            "cli@example.test",
        ]
    )
    assert ns.command == "init"
    assert ns.dir == "repo"
    assert ns.user_name == "cli"
    assert ns.user_email == "cli@example.test"


def test_cli_clone_args():
    ns = build_parser().parse_args(
        ["clone", "https://example.test/ks.git", "--dir", "parent"]
    )
    assert ns.command == "clone"
    assert ns.url == "https://example.test/ks.git"
    assert ns.dir == "parent"


class _FakeGitKeyServer:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.init_called = False

    def init(
        self,
        keys_base_branch: str = GIT_KS_KEYS_BASE_BRANCH,
        git_ks_dir: Path = GIT_KS_DIR,
    ) -> None:
        self.init_called = True
        self.keys_base_branch = keys_base_branch
        self.git_ks_dir = git_ks_dir


class _FakeGitKeyServerClient:
    def __init__(self, result: GitKSCloneResult):
        self.result = result
        self.clone_url = None
        self.clone_base_dir = None

    def clone(self, *, url, base_dir=None) -> GitKSCloneResult:
        self.clone_url = url
        self.clone_base_dir = base_dir
        return self.result


def test_cmd_init_uses_git_key_server_interface(tmp_path, capsys):
    repo = (tmp_path / "ks").resolve()
    fake = _FakeGitKeyServer(repo)
    assert cmd_init(str(repo), key_server=fake) == 0
    assert fake.init_called
    assert repo.is_dir()
    assert f"Initialised gitks repo in {repo}" in capsys.readouterr().out


def test_cmd_clone_uses_git_key_server_client_interface(tmp_path, capsys):
    dest = (tmp_path / "parent").resolve()
    dest.mkdir()
    cloned = dest / "ks"
    fake = _FakeGitKeyServerClient(
        GitKSCloneResult(
            connected=True,
            message="cloned",
            details={"status": "OK"},
            code=200,
            repo_path=cloned,
        )
    )
    assert (
        cmd_clone(
            "https://example.test/ks.git",
            str(dest),
            key_server_client=fake,
        )
        == 0
    )
    assert fake.clone_url == "https://example.test/ks.git"
    assert fake.clone_base_dir == dest
    out = capsys.readouterr().out
    assert "cloned" in out
    assert str(cloned) in out


def test_cmd_clone_returns_failure_when_not_connected(tmp_path):
    dest = (tmp_path / "parent").resolve()
    dest.mkdir()
    fake = _FakeGitKeyServerClient(
        GitKSCloneResult(
            connected=False,
            message="clone failed",
            details={"status": "CLONE_ERROR"},
            code=1,
            repo_path=None,
        )
    )
    assert (
        cmd_clone("https://example.test/ks.git", str(dest), key_server_client=fake) == 1
    )
