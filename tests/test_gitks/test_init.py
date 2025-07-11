#!/usr/bin/env python3
# coding=utf-8

"""
tests relating to ``gitks init`` operation.
"""

from pathlib import Path

import pytest
from gitbolt.git_subprocess.impl.simple import SimpleGitCommand

from gitks.core import GitKsException
from gitks.core.constants import GIT_KS_DIR, TEST_STR, FINAL_STR
from gitks.core.impl import GitKeyServerImpl


class TestSimpleInit:
    def test_no_err_when_lenient(self, repo_local):
        self.empty_repo_init_setup(repo_local)

    def test_sets_supplied_user_name(self, repo_local):
        git, _, user_name = self.empty_repo_init_setup(repo_local)
        assert (
            user_name
            == git.subcmd_unchecked.run(
                ["config", "--local", "--get", "user.name"], text=True
            ).stdout.strip()
        )

    def test_sets_supplied_user_email(self, repo_local):
        git, user_email, _ = self.empty_repo_init_setup(repo_local)
        assert (
            user_email
            == git.subcmd_unchecked.run(
                ["config", "--local", "--get", "user.email"], text=True
            ).stdout.strip()
        )

    @staticmethod
    def empty_repo_init_setup(repo_local):
        user_name = "ss"
        user_email = "ss@ss.ss"
        ks = GitKeyServerImpl(
            None, repo_local, user_name=user_name, user_email=user_email
        )
        ks.init()
        git = SimpleGitCommand(repo_local)
        return git, user_email, user_name


class TestNoMainBranchesFound:
    def test_with_lenient(self, repo_local):
        user_name = "ss"
        user_email = "ss@ss.ss"
        ks = GitKeyServerImpl(
            None, repo_local, user_name=user_name, user_email=user_email
        )
        ks.init()

    def test_errs_without_lenient(self, repo_local):
        user_name = "ss"
        user_email = "ss@ss.ss"
        ks = GitKeyServerImpl(
            None, repo_local, user_name=user_name, user_email=user_email, lenient=False
        )
        with pytest.raises(
            GitKsException, match="No base main branches found.*Lenient mode off"
        ):
            ks.init()


@pytest.mark.parametrize("lenient", [True, False])
def test_no_err_when_main_branches_found(repo_local, lenient):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = GitKeyServerImpl(None, repo_local, lenient=lenient)
    git = SimpleGitCommand(repo_local)
    git.subcmd_unchecked.run(["config", "--local", "user.name", user_name])
    git.subcmd_unchecked.run(["config", "--local", "user.email", user_email])
    a_file = Path(repo_local, "a-file")
    a_file.write_text("a-file")
    git.add_subcmd.add(".")
    git.subcmd_unchecked.run(["commit", "-m", "added a-file"])
    ks.init()


@pytest.mark.parametrize("lenient", [True, False])
def test_gitks_dir_created_when_main_branches_found(repo_local, lenient):
    test_no_err_when_main_branches_found(repo_local, lenient)
    assert Path(repo_local, GIT_KS_DIR, TEST_STR).exists()
    assert Path(repo_local, GIT_KS_DIR, FINAL_STR).exists()
