#!/usr/bin/env python3
# coding=utf-8

"""
tests relating to ``gitks init`` operation.
"""

from pathlib import Path

import pytest
from gitbolt.git_subprocess.impl.simple import SimpleGitCommand

from gitks.core import GitKsException
from gitks.core.constants import (
    GIT_KS_DIR,
    TEST_STR,
    FINAL_STR,
    GIT_KS_DIR_CONFIG_KEY,
    GIT_KS_BRANCH_CONFIG_KEY,
    KEYSERVER_CONFIG_KEY,
    GIT_KS_STR, GIT_KS_KEYS_BASE_BRANCH,
)
from gitks.core.impl import WorkTreeGitKeyServerImpl, BaseDirWorkTreeGenerator, WorkTreeGenerator


@pytest.fixture
def worktree_for_test(tmp_path) -> WorkTreeGenerator:
    return BaseDirWorkTreeGenerator(Path(tmp_path, 'keys-base'))


class TestSimpleInit:
    def test_no_err_run(self, repo_local, worktree_for_test):
        self.empty_repo_init_setup(repo_local, worktree_for_test)

    def test_sets_supplied_user_name(self, repo_local, worktree_for_test):
        git, _, user_name = self.empty_repo_init_setup(repo_local, worktree_for_test)
        assert (
            user_name
            == git.subcmd_unchecked.run(
                ["config", "--local", "--get", "user.name"], text=True
            ).stdout.strip()
        )

    def test_sets_supplied_user_email(self, repo_local, worktree_for_test):
        git, user_email, _ = self.empty_repo_init_setup(repo_local, worktree_for_test)
        assert (
            user_email
            == git.subcmd_unchecked.run(
                ["config", "--local", "--get", "user.email"], text=True
            ).stdout.strip()
        )

    @pytest.mark.parametrize("keys_branch", ["test", "final"])
    def test_sets_keys_worktree(self, repo_local, worktree_for_test, keys_branch):
        git, worktree_details = self._sets_keys_worktree(repo_local, worktree_for_test)
        assert (
            f"branch refs/heads/{GIT_KS_KEYS_BASE_BRANCH}/{keys_branch}"
            in worktree_details
        )

    @pytest.mark.parametrize("keys_branch", ["test", "final"])
    def test_sets_keys_worktree(self, repo_local, worktree_for_test, keys_branch):
        git, worktree_details = self._sets_keys_worktree(repo_local, worktree_for_test)
        assert (
            f"refs/heads/{GIT_KS_KEYS_BASE_BRANCH}/{keys_branch}"
            in worktree_details
        )

    @pytest.mark.parametrize("keys_branch", ["test", "final"])
    def test_sets_keys_worktree_in_base_dir(self, repo_local, worktree_for_test, keys_branch):
        git, worktree_details = self._sets_keys_worktree(repo_local, worktree_for_test)
        assert worktree_details[f"refs/heads/{GIT_KS_KEYS_BASE_BRANCH}/{keys_branch}"][0].is_relative_to(Path(repo_local).parent)

    def _sets_keys_worktree(self, repo_local, worktree_for_test) -> tuple[SimpleGitCommand, dict[str, tuple[Path, str]]]:
        git, _, _ = self.empty_repo_init_setup(repo_local, worktree_for_test)
        worktree_details_lst = git.subcmd_unchecked.run(
                ["worktree", "list", "--porcelain", "-z"], text=True
            ).stdout.strip().split("\0")
        worktree_details: dict[str, tuple[Path, str]] = dict()
        i=0
        while i < len(worktree_details_lst):
            if worktree_details_lst[i].strip() == '':
                i += 1
                continue

            path = Path(worktree_details_lst[i].strip().split(maxsplit=1)[1])
            i += 1
            head = worktree_details_lst[i].strip().split(maxsplit=1)[1]
            i += 1
            ref = worktree_details_lst[i].strip().split(maxsplit=1)[1]
            worktree_details[ref] = path, head
            i += 2

        return git, worktree_details

    @staticmethod
    def empty_repo_init_setup(repo_local, worktree_for_test):
        user_name = "ss"
        user_email = "ss@ss.ss"
        ks = WorkTreeGitKeyServerImpl(
            None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name=user_name, user_email=user_email,
            worktree_generator=worktree_for_test
        )
        ks.init()
        git = SimpleGitCommand(repo_local)
        return git, user_email, user_name


def test_no_err_when_main_branches_found(repo_local, worktree_for_test):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = WorkTreeGitKeyServerImpl(
        None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, worktree_generator=worktree_for_test)
    git = SimpleGitCommand(repo_local)
    git.subcmd_unchecked.run(["config", "--local", "user.name", user_name])
    git.subcmd_unchecked.run(["config", "--local", "user.email", user_email])
    a_file = Path(repo_local, "a-file")
    a_file.write_text("a-file")
    git.add_subcmd.add(".")
    git.subcmd_unchecked.run(["commit", "-m", "added a-file"])
    ks.init()


def test_gitks_dir_created_when_main_branches_found(repo_local, worktree_for_test):
    test_no_err_when_main_branches_found(repo_local, worktree_for_test)
    assert Path(repo_local, GIT_KS_DIR, TEST_STR).exists()
    assert Path(repo_local, GIT_KS_DIR, FINAL_STR).exists()


def test_registers_gitks_dir_if_different_supplied(repo_local, worktree_for_test):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = WorkTreeGitKeyServerImpl(
        None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name, user_email,
            worktree_generator=worktree_for_test)
    ano_gitks_home = Path(".ano-gpg-home", ".ano-gitks")
    ks.init(git_ks_dir=ano_gitks_home)
    git = SimpleGitCommand(repo_local)
    assert git.subcmd_unchecked.run(
        ["config", "--local", "--get", GIT_KS_DIR_CONFIG_KEY], text=True
    ).stdout.strip() == str(ano_gitks_home)


def test_registers_branch_name_if_different_supplied(repo_local, worktree_for_test):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = WorkTreeGitKeyServerImpl(
        None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name, user_email,
            worktree_generator=worktree_for_test)
    ano_gitks_branch = "ano-gitks/keys"
    ks.init(keys_base_branch=ano_gitks_branch)
    git = SimpleGitCommand(repo_local)
    assert (
        git.subcmd_unchecked.run(
            ["config", "--local", "--get", GIT_KS_BRANCH_CONFIG_KEY], text=True
        ).stdout.strip()
        == ano_gitks_branch
    )


def test_registration_even_if_defaults_are_used(repo_local, worktree_for_test):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = WorkTreeGitKeyServerImpl(
        None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name, user_email,
            worktree_generator=worktree_for_test)
    git = SimpleGitCommand(repo_local)
    ks.init()
    assert GIT_KS_KEYS_BASE_BRANCH == git.subcmd_unchecked.run(
            ["config", "--local", "--get", GIT_KS_BRANCH_CONFIG_KEY], text=True
        ).stdout.strip()
    assert str(GIT_KS_DIR) == git.subcmd_unchecked.run(
            ["config", "--local", "--get", GIT_KS_DIR_CONFIG_KEY], text=True
        ).stdout.strip()


@pytest.mark.parametrize('keys_branch', ['gitks/keys-branch', 'gitks-keys-branch', 'keys-branch'])
class TestBranchCreations:
    def test_errs_if_keys_base_branch_already_exists(self, repo_local, keys_branch, worktree_for_test):
        git, ks = self._prep_branch(repo_local, worktree_for_test)
        git.subcmd_unchecked.run(["branch", keys_branch])
        with pytest.raises(
            GitKsException,
            match=f"Requested keys base branch {keys_branch} already exists. Rerun with a different branch name.",
        ):
            ks.init(keys_base_branch=keys_branch)

    def test_errs_if_keys_test_branch_already_exists(self, repo_local, keys_branch, worktree_for_test):
        git, ks = self._prep_branch(repo_local, worktree_for_test)
        git.subcmd_unchecked.run(["branch", f"{keys_branch}/{TEST_STR}"])
        with pytest.raises(
            GitKsException,
            match=f"Requested keys base branch {keys_branch} already exists. Rerun with a different branch name.",
        ):
            ks.init(keys_base_branch=keys_branch)

    def test_errs_if_keys_final_branch_already_exists(self, repo_local, keys_branch, worktree_for_test):
        git, ks = self._prep_branch(repo_local, worktree_for_test)
        git.subcmd_unchecked.run(["branch", f"{keys_branch}/{FINAL_STR}"])
        with pytest.raises(
            GitKsException,
            match=f"Requested keys base branch {keys_branch} already exists. Rerun with a different branch name.",
        ):
            ks.init(keys_base_branch=keys_branch)

    @staticmethod
    def _prep_branch(repo_local, worktree_for_test):
        user_name = "ss"
        user_email = "ss@ss.ss"
        ks = WorkTreeGitKeyServerImpl(
            None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name, user_email,
            worktree_generator=worktree_for_test)
        git = SimpleGitCommand(repo_local)
        git.subcmd_unchecked.run(["config", "--local", "user.name", user_name])
        git.subcmd_unchecked.run(["config", "--local", "user.email", user_email])
        a_file = Path(repo_local, "a-file")
        a_file.write_text("a-file")
        git.add_subcmd.add(".")
        git.subcmd_unchecked.run(["commit", "-m", "added a-file"])
        return git, ks


def test_register_gitks_as_keyserver_on_success(repo_local, worktree_for_test):
    user_name = "ss"
    user_email = "ss@ss.ss"
    ks = WorkTreeGitKeyServerImpl(
        None, # type: ignore[arg-type] # required KeyValidator, provided None
            repo_local, user_name, user_email,
            worktree_generator=worktree_for_test)
    ks.init()
    git = SimpleGitCommand(repo_local)
    assert (
        git.subcmd_unchecked.run(
            ["config", "--local", "--get", KEYSERVER_CONFIG_KEY], text=True
        ).stdout.strip()
        == GIT_KS_STR
    )
