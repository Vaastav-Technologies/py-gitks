#!/usr/bin/env python3

"""Factory returns the worktree implementation behind gitks interfaces."""

from unittest.mock import patch

from gitks.core.factory import git_key_server, git_key_server_client, worktrees_dir
from gitks.core.gpg_validator import GPGKeyValidator
from gitks.core.impl import WorkTreeGitKeyServerImpl


def test_worktrees_dir_is_under_parent(tmp_path):
    parent = tmp_path / "parent"
    assert worktrees_dir(parent) == parent.resolve() / ".gitks-worktrees"


@patch("gitks.core.impl.get_git_config_ks", return_value=GPGKeyValidator())
def test_git_key_server_returns_worktree_implementation(mock_validator, tmp_path):
    repo = tmp_path / "repo"
    ks = git_key_server(repo, worktrees_parent=tmp_path)
    assert isinstance(ks, WorkTreeGitKeyServerImpl)
    assert ks.root_dir == repo
    mock_validator.assert_called_once()


@patch("gitks.core.impl.get_git_config_ks", return_value=GPGKeyValidator())
def test_git_key_server_client_returns_worktree_implementation(mock_validator, tmp_path):
    repo = tmp_path / "repo"
    client = git_key_server_client(
        repo,
        clone_base_dir=tmp_path,
        worktrees_parent=tmp_path,
    )
    assert isinstance(client, WorkTreeGitKeyServerImpl)
    assert client.clone_base_dir == tmp_path
    mock_validator.assert_called_once()
