#!/usr/bin/env python3
# coding=utf-8

"""
implementations related to keyserver workings for ``gitks``.
"""

import logging
import random
import string
import subprocess
import typing
from abc import abstractmethod
from pathlib import Path
from subprocess import CalledProcessError
from typing import override, Protocol, overload

from gitbolt.git_subprocess.base import GitCommand
from gitbolt.git_subprocess.impl.simple import SimpleGitCommand
from logician.configurators.env import VTEnvListLC
from logician.std_log.configurator import StdLoggerConfigurator
from vt.utils.commons.commons.op import RootDirOp
from vt.utils.errors.error_specs import ERR_STATE_ALREADY_EXISTS, ERR_GENERIC_ERR

from gitks.core.base import GitKeyServer, KeyValidator, GitKeyServerClient
from gitks.core.constants import (
    GIT_KS_DIR,
    GIT_KS_KEYS_BASE_BRANCH,
    TEST_STR,
    FINAL_STR,
    GIT_KS_BRANCH_CONFIG_KEY,
    GIT_KS_DIR_CONFIG_KEY,
    KEYSERVER_CONFIG_KEY,
    GIT_KS_STR, REPO_CONF_BRANCH, SELF_REPO,
)
from gitks.core.errors import GitKsException
from gitks.core.model import KeyDeleteResult, KeyData, KeyUploadResult, KeyServerConnectResult, GitSelf, \
    GitKSCloneResult
from gitks.core.utils import extract_repo_name, is_git_repo

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


class WorkTreeGitKeyServerImpl(GitKeyServer, GitKeyServerClient, RootDirOp):

    def __init__(
        self,
        key_validator: KeyValidator,
        repo_root_dir: Path | None = None,
        user_name: str | None = None,
        user_email: str | None = None,
        worktree_generator: WorkTreeGenerator | None = None,
        clone_base_dir: Path = Path.home()
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
        :param clone_base_dir: Repo will be cloned to this base location upon clone operation.
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
        self.clone_base_dir = clone_base_dir
        logger.debug(f"clone_base_dir: {self.clone_base_dir}")
        logger.trace("Exiting")

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
            repo_conf_worktree_details = worktree_map.get(repo_conf_branch)
            repo_conf_worktree = repo_conf_worktree_details.get("worktree")
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

    @overload
    @override
    def clone(self, *, url: GitSelf = SELF_REPO, base_dir: GitSelf = SELF_REPO) -> GitKSCloneResult:
        ...

    @overload
    @override
    def clone(self, *, url: str, base_dir: Path | None = None) -> GitKSCloneResult:
        ...

    @override
    def clone(self, *, url: str | GitSelf = SELF_REPO, base_dir: Path | None | GitSelf = SELF_REPO) -> GitKSCloneResult:
        """
        Examples:

        >>> test_obj = WorkTreeGitKeyServerImpl(None) # type: ignore[arg-type] # required KeyValidator got None

        * Error scenarios

        * ``url`` and ``base_dir`` both should be ``SELF_REPO``.

        >>> test_obj.clone(url=SELF_REPO, base_dir=Path()) # type: ignore[arg-type] # required both SELF_REPO
        Traceback (most recent call last):
        gitks.core.errors.GitKsException: ValueError: SELF_REPO url does not allow base_dir configuration.

        >>> test_obj.clone(url="", base_dir=SELF_REPO) # type: ignore[arg-type] # required both SELF_REPO
        Traceback (most recent call last):
        gitks.core.errors.GitKsException: ValueError: SELF_REPO base_dir does not allow url configuration.

        * Assumes ``url`` and ``base_dir`` both as ``SELF_REPO`` if none of them are provided.

        >>> assert Path.cwd() == test_obj.clone().repo_path # SELF_REPO denotes current repo path

        """
        logger.trace("Entering")
        logger.debug(f"url: {url}")
        logger.debug(f"base_dir: {base_dir}")
        if url == SELF_REPO and base_dir != SELF_REPO:
            errmsg = "SELF_REPO url does not allow base_dir configuration."
            logger.error(errmsg)
            raise GitKsException(errmsg) from ValueError(errmsg)

        if base_dir == SELF_REPO and url != SELF_REPO:
            errmsg = "SELF_REPO base_dir does not allow url configuration."
            logger.error(errmsg)
            raise GitKsException(errmsg) from ValueError(errmsg)

        if base_dir == SELF_REPO and url == SELF_REPO:
            message = "No clone needed as repo itself is the keyserver."
            logger.notice(message)
            logger.info("No-op")
            return GitKSCloneResult(connected=True,
                                    message=message,
                                    repo_path=self.repo_root_dir,
                                    code=200,
                                    details=dict(status="OK", operation="NOOP"))

        base_dir = base_dir or self.clone_base_dir
        logger.debug(f"computed base_dir: {base_dir}")
        logger.debug("Trying to clone the repo in desired base_dir.")
        repo_name = extract_repo_name(url)
        logger.debug(f"Extracted repo name: {repo_name}")
        repo_dir = Path(base_dir, repo_name)
        logger.debug(f"repo_dir: {repo_dir}")
        if is_git_repo(repo_dir):
            message = f"Repo already cloned at {repo_dir}"
            logger.notice(f"{message}. skipping clone..")
            return GitKSCloneResult(connected=True,
                                    message=message,
                                    repo_path=repo_dir,
                                    code=200,
                                    details=dict(status="ALREADY_EXISTS", operation="NOOP"))

        logger.debug(f"Cloning the repo in repo_dir: {repo_dir}")
        try:
            clone_cmd = ["git", "clone", url, str(repo_dir)]
            logger.debug(f"Running: {clone_cmd}")
            completed_process = subprocess.run(clone_cmd, capture_output=True,
                                               check=True, text=True)
            logger.trace("Exiting")
            return GitKSCloneResult(connected=True,
                                    message=completed_process.stderr,
                                    repo_path=repo_dir,
                                    code=completed_process.returncode,
                                    details=dict(status="ALREADY_EXISTS", operation="clone",
                                                 out=completed_process.stdout))
        except CalledProcessError as e:
            logger.error(f"Error `{e}` while cloning repo `{repo_name}` from url `{url}`")
            raise GitKsException(f"Error chile cloning repo: {repo_name}", exit_code=e.returncode,
                                 connected=False, message=e.stderr, code=e.returncode, status="CLONE_ERROR",
                                 operation="clone", out=e.output, cmd=e.cmd) from e

    def register(self, url: str) -> KeyServerConnectResult:
        return self.clone(url=url)

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


@typing.no_type_check
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
