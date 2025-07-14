#!/usr/bin/env python3
# coding=utf-8

"""
implementations related to keyserver workings for ``gitks``.
"""

import logging
import random
import string
from abc import abstractmethod
from pathlib import Path
from typing import override, Protocol

from gitbolt.git_subprocess.base import GitCommand
from gitbolt.git_subprocess.impl.simple import SimpleGitCommand
from logician.configurators.env import VTEnvListLC
from logician.std_log.configurator import StdLoggerConfigurator
from vt.utils.commons.commons.op import RootDirOp
from vt.utils.errors.error_specs import ERR_STATE_ALREADY_EXISTS

from gitks.core.base import GitKeyServer, KeyValidator
from gitks.core.constants import (
    GIT_KS_DIR,
    GIT_KS_KEYS_BASE_BRANCH,
    TEST_STR,
    FINAL_STR,
    GIT_KS_BRANCH_CONFIG_KEY,
    GIT_KS_DIR_CONFIG_KEY,
    KEYSERVER_CONFIG_KEY,
    GIT_KS_STR, REPO_CONF_BRANCH,
)
from gitks.core.errors import GitKsException
from gitks.core.model import KeyDeleteResult, KeyData, KeyUploadResult

_base_logger = logging.getLogger(__name__)
logger = VTEnvListLC(["GITKS_LOG"], StdLoggerConfigurator()).configure(_base_logger)


class WorkTreeGenerator(Protocol):
    """
    Interface to generate a git worktree.
    """

    @abstractmethod
    def generate_worktree(self, repo_path: Path, for_branch: str, *for_branches: str, orphan: bool = False) -> Path:
        """
        Generate git work tree for ``for_branch``.

        :param repo_path: path to the repo root directory.
        :param for_branch: the branch for which git worktree needs to be generated.
        :param orphan: Create an orphan branch and then the worktree? This puts and empty commit on the orphan worktree
            to make it persistent. The worktree is erased in the next run if it has no commits.
        :return: Path to the generated worktree base directory.
        """
        ...


class BaseDirWorkTreeGenerator(WorkTreeGenerator, RootDirOp):

    def __init__(self, base_dir: Path = Path.home(), git: GitCommand | None = None, random_dir_len: int = 10):
        """
        Generate worktrees for branches in a base directory.

        :param base_dir: the base directory to generate worktrees in. Defaults to user's home directory
            if this parameter is not provided.
        :param git: the git object.
        :param random_dir_len: length of the random directory which will be inside ``base_dir`` to have worktrees
            created into.
        """
        logger.trace("Entering")
        self.base_dir = base_dir
        logger.debug(f"base_dir: {base_dir}")
        self.git = git
        logger.debug(f"git: {git}")
        self.random_dir_len = random_dir_len
        logger.debug(f"random_dir_len: {random_dir_len}")
        logger.trace("Exiting")

    @override
    def generate_worktree(self, repo_path: Path, for_branch: str, *for_branches: str, orphan: bool = False) -> Path:
        logger.trace("Entering")
        logger.debug(f"repo_path: {repo_path}")
        logger.debug(f"for_branch: {for_branch}")
        logger.debug(f"for_branches: {for_branches}")
        logger.debug(f"orphan: {orphan}")
        random_dir_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(self.random_dir_len))
        random_base_dir = Path(self.base_dir, random_dir_str)
        logger.debug(f"random_base_dir: {random_base_dir}")
        git = self.git or SimpleGitCommand(repo_path)
        logger.debug(f"Got git object: {git}")
        branches = [for_branch, *for_branches]
        for branch in branches:
            branch_dir = Path(random_base_dir, branch)
            logger.debug(f"branch_dir: {branch_dir}")
            cmd_to_run = ["worktree", "add", str(branch_dir)]
            if orphan:
                cmd_to_run += ["--orphan"]
            cmd_to_run += ["-b", branch]
            logger.debug(f"cmd_to_run: {cmd_to_run}")
            git.subcmd_unchecked.run(cmd_to_run)
            logger.debug(f"worktree created for branch {branch} at path: {branch_dir}")
            if orphan:
                commit_cmd_to_run = ["commit", "-m", f"initial commit for branch: {branch}", "--allow-empty"]
                git.git_opts_override(C=[branch_dir]).subcmd_unchecked.run(commit_cmd_to_run)
                logger.debug(f"Empty commit created for orphan worktree branch: {branch}")
        logger.trace("Exiting")
        return random_base_dir

    @property
    def root_dir(self) -> Path:
        return self.base_dir


class WorkTreeGitKeyServerImpl(GitKeyServer, RootDirOp):
    def __init__(
        self,
        key_validator: KeyValidator,
        repo_root_dir: Path | None = None,
        user_name: str | None = None,
        user_email: str | None = None,
        worktree_generator: WorkTreeGenerator | None = None
    ):
        """
        Get a ``GitKeyServer`` which maintains its keys in branches on worktrees.

        :param key_validator: The validator for keys.
        :param repo_root_dir: root directory of the git repo.
        :param user_name: git's ``user.name``. Will take the global ``user.name`` if not provided.
        :param user_email: git's ``user.email``. Will take global ``user.email`` if not provided.
        :param worktree_generator: A generator which generates worktrees for keys branches. Defaults to generating
            worktrees directly at user's home directory if this parameter is not provided. This decision is mostly ok
            for most cases.
        """
        logger.trace("Entering")
        self._key_validator = key_validator
        logger.debug(f"key_validator: {key_validator}")
        logger.debug(f"Supplied repo_root_dir: {repo_root_dir}")
        self.repo_root_dir = repo_root_dir or Path.cwd()
        logger.debug(f"computed repo_root_dir: {repo_root_dir}")
        logger.trace("Exiting")
        self.git = SimpleGitCommand(self.repo_root_dir)
        self.user_name = user_name
        if user_name:  # else autodetect
            self.git = self.git.git_envs_override(
                GIT_AUTHOR_NAME=user_name
            ).git_envs_override(GIT_COMMITTER_NAME=user_name)
        self.user_email = user_email
        if user_email:  # else autodetect
            self.git = self.git.git_envs_override(
                GIT_AUTHOR_EMAIL=user_email
            ).git_envs_override(GIT_COMMITTER_EMAIL=user_email)
        logger.debug(f"supplied worktree_generator: {worktree_generator}")
        self.worktree_generator = worktree_generator or BaseDirWorkTreeGenerator(Path.home())
        logger.debug(f"computed worktree_generator: {worktree_generator}")

    @override
    def init(
        self,
        keys_base_branch: str = GIT_KS_KEYS_BASE_BRANCH,
        git_ks_dir: Path = GIT_KS_DIR,
    ) -> None:
        logger.trace("Entering")
        logger.debug(f"git_ks_dir: {git_ks_dir}")
        logger.debug(f"key_base_branch: {keys_base_branch}")

        logger.info(f"Initialising git repo in {self.root_dir}")
        self.git.subcmd_unchecked.run(["init"])
        logger.debug("repo initialised.")

        if self.user_name:
            self.git.subcmd_unchecked.run(
                ["config", "--local", "user.name", self.user_name]
            )
            logger.debug(f"Set local git.user.name: {self.user_name}")
        if self.user_email:
            self.git.subcmd_unchecked.run(
                ["config", "--local", "user.email", self.user_email]
            )
            logger.debug(f"Set local git.user.email: {self.user_email}")

        logger.debug("Checking if repo configuration branch exists already.")
        repo_conf_branch = self.git.subcmd_unchecked.run(["branch", "--list", REPO_CONF_BRANCH],
                                                         text=True).stdout.strip()
        if repo_conf_branch:
            logger.info(f"Repo configuration branch '{REPO_CONF_BRANCH}' already exists.")
            logger.debug(f"Checking if worktree for {REPO_CONF_BRANCH} is already present.")
            worktree_str = self.git.subcmd_unchecked.run(["worktree", "list", "--porcelain", "-z"]).stdout.strip()
            # TODO: send a feature request to git to provide worktree with
            #  either a git worktree list --get <branch-pattern>
            #  or simplt git worktree list <branch-pattern>
            worktree_map = parse_git_worktree_branches_only(worktree_str)
            repo_conf_worktree = worktree_map.get(repo_conf_branch)
            if not repo_conf_worktree:
                logger.debug("Repo conf branch worktree does not exist.")
                repo_conf_worktree = self.worktree_generator.generate_worktree(self.git.root_dir, repo_conf_branch)
                logger.debug(f"Created repo conf branch worktree")
        else:
            logger.info("Creating repo configuration branch.")
            repo_conf_worktree = self.worktree_generator.generate_worktree(self.git.root_dir,
                                                                           REPO_CONF_BRANCH, orphan=True)
            logger.debug(f"Created repo conf branch worktree")
        logger.debug(f"repo_conf_worktree path: {repo_conf_worktree}")
        repo_conf_worktree = Path(repo_conf_worktree, REPO_CONF_BRANCH)
        repo_conf_worktree_ks_file = Path(repo_conf_worktree, "KEYSERVER")
        repo_conf_worktree_ks_file.write_text(GIT_KS_STR)
        repo_conf_worktree_ks_url_file = Path(repo_conf_worktree, "KEYSERVER.URL")
        repo_conf_worktree_ks_url_file.write_text("SELF")   # denote that the git keyserver is on the same repo
        repo_conf_worktree_ks_path_file = Path(repo_conf_worktree, "KEYSERVER.PATH")
        repo_conf_worktree_ks_path_file.write_text("SELF")   # denote that the git keyserver is on the same repo
        repo_conf_worktree_git = self.git.git_opts_override(C=[repo_conf_worktree])
        repo_conf_worktree_git.add_subcmd.add(str(repo_conf_worktree_ks_file), str(repo_conf_worktree_ks_url_file),
                                              str(repo_conf_worktree_ks_path_file))
        repo_conf_worktree_git.subcmd_unchecked.run(["commit", "-m", "git keyserver config added."])
        logger.info("Configuration saved in repo conf branch.")

        logger.debug("Checking if supplied keys base branch exists already.")
        existing_branches = self.git.subcmd_unchecked.run(
            ["branch", "--list", f"{keys_base_branch}*"], text=True
        ).stdout.split()

        keys_test_branch = f"{keys_base_branch}/{TEST_STR}"
        keys_final_branch = f"{keys_base_branch}/{FINAL_STR}"
        if keys_base_branch in existing_branches or keys_test_branch in existing_branches or keys_final_branch in existing_branches:
            errmsg = f"Requested keys base branch {keys_base_branch} already exists. Rerun with a different branch name."
            logger.error(errmsg)
            raise GitKsException(errmsg, exit_code=ERR_STATE_ALREADY_EXISTS)

        logger.debug(f"Attempting to create keys base branches {keys_base_branch}")
        worktree_path = self.worktree_generator.generate_worktree(self.git.root_dir, keys_test_branch, keys_final_branch,
                                                  orphan=True)
        logger.debug(f"Worktrees generated in {worktree_path}")

        self.git.subcmd_unchecked.run(
            ["config", "--local", GIT_KS_BRANCH_CONFIG_KEY, keys_base_branch]
        )
        logger.debug(f"Registered {GIT_KS_BRANCH_CONFIG_KEY}={keys_base_branch}")
        logger.info(f"key base branch {keys_base_branch} created.")

        git_ks_test_dir = Path(self.root_dir, git_ks_dir, TEST_STR)
        logger.debug(f"attempting to create test directory: {git_ks_test_dir}")
        git_ks_test_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_test_dir} created.")
        git_ks_final_dir = Path(self.root_dir, git_ks_dir, FINAL_STR)
        logger.debug(f"attempting to create final directory: {git_ks_final_dir}")
        git_ks_final_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_final_dir} created.")
        self.git.subcmd_unchecked.run(
            ["config", "--local", GIT_KS_DIR_CONFIG_KEY, str(git_ks_dir)]
        )
        logger.debug(f"Registered {GIT_KS_DIR_CONFIG_KEY}={str(git_ks_dir)}")

        self.git.subcmd_unchecked.run(
            ["config", "--local", KEYSERVER_CONFIG_KEY, GIT_KS_STR]
        )
        logger.info(f"Registered 'gitks' as the {KEYSERVER_CONFIG_KEY}")

        logger.success("Initialised gitks.")
        logger.trace("Exiting")

    @override
    def send_key(self, public_key: bytes | str) -> KeyUploadResult:
        pass

    @override
    def receive_key(self, key_id: str) -> bytes | str:
        pass

    @override
    def search_keys(self, key_search_str: str) -> list[KeyData]:
        pass

    @override
    def delete_key(self, key_id: str) -> KeyDeleteResult:
        pass

    @override
    @property
    def root_dir(self) -> Path:
        return self.repo_root_dir

    @override
    @property
    def key_validator(self) -> KeyValidator:
        return self._key_validator


def parse_git_worktree_branches_only(data: bytes):
    worktrees = {}
    entries = data.split(b'\0')

    current = {}
    for entry in entries:
        if not entry:
            # End of a worktree block
            branch = current.get("branch")
            if branch:
                worktrees[branch] = current
            current = {}
            continue

        if b' ' in entry:
            key, value = entry.split(b' ', 1)
            current[key.decode()] = value.decode()
        else:
            current[entry.decode()] = True  # flag like 'prunable' or 'locked'

    return worktrees
