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

from gitbolt.subprocess.base import GitCommand
from gitbolt.subprocess.impl.simple import SimpleGitCommand
from logician.configurators.env import LgcnEnvListLC
from logician.stdlog.configurator import StdLoggerConfigurator
from vt.utils.commons.commons.op import RootDirOp
from vt.utils.errors.error_specs import ERR_STATE_ALREADY_EXISTS, ERR_INVALID_USAGE

from gitks.core.base import GitKeyServer, KeyValidator, GitKeyServerClient
from gitks.core.constants import (
    GIT_KS_DIR,
    GIT_KS_KEYS_BASE_BRANCH,
    TEST_STR,
    FINAL_STR,
    DENIED_STR,
    REQUESTS_STR,
    APPROVED_STR,
    GIT_KS_BRANCH_CONFIG_KEY,
    GIT_KS_DIR_CONFIG_KEY,
    GIT_KS_STR,
    REPO_CONF_BRANCH,
    SELF_REPO,
    CAPS_KEYSERVER_STR,
    KEYSERVER_URL_F_NAME,
    GIT_KS_KEYSERVER_PATH_KEY,
    KEYSERVER_BRANCH_F_NAME,
)
from gitks.core.errors import GitKsException
from gitks.core.gpg import (
    first_secret_key_id,
    get_key_name_from_key_data as gpg_get_key_name_from_key_data,
    get_key_user_email as gpg_get_key_user_email,
    get_key_user_name as gpg_get_key_user_name,
    make_detached_signature,
    owner_sign_data,
    verify_detached_signature,
)
from gitks.core.model import (
    KeyDeleteResult,
    KeyData,
    KeyUploadResult,
    KeyUploadStatus,
    KeyReviewResult,
    KeyReviewStatus,
    PendingKey,
    KeyServerConnectResult,
    GitSelf,
    GitKSCloneResult,
)
from gitks.core.utils import extract_repo_name, index_user_email, index_user_name, is_git_repo

_base_logger = logging.getLogger(__name__)
logger = LgcnEnvListLC(["GITKS_LOG"], StdLoggerConfigurator()).configure(_base_logger)


class WorkTreeGenerator(Protocol):
    """
    Interface to generate a git worktree.
    """

    @abstractmethod
    def generate_worktree(
        self, repo_path: Path, for_branch: str, *for_branches: str, orphan: bool = False
    ) -> Path:
        """
        Generate git work tree for ``for_branch``.

        :param repo_path: path to the repo root directory.
        :param for_branch: the branch for which git worktree needs to be generated.
        :param orphan: Create an orphan branch and then the worktree. This puts and empty commit on the orphan worktree
            to make it persistent. The worktree is erased in the next run if it has no commits.
        :return: Path to the generated worktree base directory.
        """
        ...


class BaseDirWorkTreeGenerator(WorkTreeGenerator, RootDirOp):
    def __init__(
        self,
        base_dir: Path = Path.home(),
        git: GitCommand | None = None,
        random_dir_len: int = 10,
    ):
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
    def generate_worktree(
        self, repo_path: Path, for_branch: str, *for_branches: str, orphan: bool = False
    ) -> Path:
        logger.trace("Entering")
        logger.debug(f"repo_path: {repo_path}")
        logger.debug(f"for_branch: {for_branch}")
        logger.debug(f"for_branches: {for_branches}")
        logger.debug(f"orphan: {orphan}")
        random_dir_str = "".join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(self.random_dir_len)
        )
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
            git.subcmd_unchecked().run(cmd_to_run)
            logger.debug(f"worktree created for branch {branch} at path: {branch_dir}")
            if orphan:
                commit_cmd_to_run = [
                    "commit",
                    "-m",
                    f"initial commit for branch: {branch}",
                    "--allow-empty",
                ]
                git.git_opts_override(C=[branch_dir]).subcmd_unchecked().run(
                    commit_cmd_to_run
                )
                logger.debug(
                    f"Empty commit created for orphan worktree branch: {branch}"
                )
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
        clone_base_dir: Path = Path.home(),
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
        logger.debug(f"Supplied user_name: {user_name}")
        logger.debug(f"Supplied user_email: {user_email}")
        self.git = SimpleGitCommand(self.repo_root_dir)
        logger.debug(f"Obtained git instance: {self.git}")
        self.user_name = user_name
        if user_name:  # else autodetect
            self.git = self.git.git_envs_override(
                GIT_AUTHOR_NAME=user_name, GIT_COMMITTER_NAME=user_name
            )
        self.user_email = user_email
        if user_email:  # else autodetect
            self.git = self.git.git_envs_override(
                GIT_AUTHOR_EMAIL=user_email, GIT_COMMITTER_EMAIL=user_email
            )
        logger.debug(f"Obtained git instance: {self.git}")
        logger.debug(f"supplied worktree_generator: {worktree_generator}")
        self.worktree_generator = worktree_generator or BaseDirWorkTreeGenerator(
            Path.home()
        )
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

        logger.debug(f"Initialising git repo in {self.root_dir}")
        self.git.subcmd_unchecked().run(["init"])
        logger.info(f"Initialised git repo in {self.root_dir}")

        self.set_local_user_info()

        logger.debug("Checking if supplied keys base branch exists already.")
        existing_branches = self.git.subcmd_unchecked().run(
            ["branch", "--list", f"{keys_base_branch}*"], text=True
        ).stdout.split()

        keys_test_branch = f"{keys_base_branch}/{TEST_STR}"
        keys_final_branch = f"{keys_base_branch}/{FINAL_STR}"
        keys_denied_branch = f"{keys_base_branch}/{DENIED_STR}"
        if (
            keys_base_branch in existing_branches
            or keys_test_branch in existing_branches
            or keys_final_branch in existing_branches
            or keys_denied_branch in existing_branches
        ):
            errmsg = f"Requested keys base branch {keys_base_branch} already exists. Rerun with a different branch name."
            logger.error(errmsg)
            raise GitKsException(errmsg, exit_code=ERR_STATE_ALREADY_EXISTS)

        logger.debug(f"Attempting to create keys base branches {keys_base_branch}")
        worktree_path = self.worktree_generator.generate_worktree(
            self.git.root_dir,
            keys_test_branch,
            keys_final_branch,
            keys_denied_branch,
            orphan=True,
        )
        logger.debug(f"Keys base branch worktrees generated in {worktree_path}")
        logger.debug(f"{keys_test_branch} -> {worktree_path / keys_test_branch}")
        logger.debug(f"{keys_final_branch} -> {worktree_path / keys_final_branch}")
        logger.debug(f"{keys_denied_branch} -> {worktree_path / keys_denied_branch}")
        logger.info(f"key base branch {keys_base_branch} created.")

        git_ks_test_dir = Path(self.root_dir, git_ks_dir, TEST_STR)
        logger.debug(
            f"attempting to create keyserver keys test directory: {git_ks_test_dir}"
        )
        git_ks_test_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_test_dir} created.")
        git_ks_final_dir = Path(self.root_dir, git_ks_dir, FINAL_STR)
        logger.debug(
            f"attempting to create keyserver keys final directory: {git_ks_final_dir}"
        )
        git_ks_final_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_final_dir} created.")
        git_ks_denied_dir = Path(self.root_dir, git_ks_dir, DENIED_STR)
        logger.debug(
            f"attempting to create keyserver keys denied directory: {git_ks_denied_dir}"
        )
        git_ks_denied_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_denied_dir} created.")
        self.git.subcmd_unchecked().run(
            ["config", "--local", GIT_KS_DIR_CONFIG_KEY, str(git_ks_dir)]
        )
        logger.debug(f"Registered {GIT_KS_DIR_CONFIG_KEY}={str(git_ks_dir)}")

        logger.debug("Checking if repo configuration branch exists already.")
        repo_conf_branch = self.git.subcmd_unchecked().run(
            ["branch", "--list", REPO_CONF_BRANCH], text=True
        ).stdout.strip()
        if repo_conf_branch:
            logger.info(
                f"Repo configuration branch '{REPO_CONF_BRANCH}' already exists."
            )
            logger.debug(
                f"Checking if worktree for {REPO_CONF_BRANCH} is already present."
            )
        else:
            logger.info("Creating repo configuration branch.")
            self.worktree_generator.generate_worktree(
                self.git.root_dir, REPO_CONF_BRANCH, orphan=True
            )
            logger.debug("Created repo conf branch worktree")
        repo_conf_worktree = self.worktree_dir_for(REPO_CONF_BRANCH)
        logger.debug(f"repo_conf_worktree path: {repo_conf_worktree}")
        repo_conf_worktree_ks_file = Path(repo_conf_worktree, CAPS_KEYSERVER_STR)
        repo_conf_worktree_ks_file.write_text(GIT_KS_STR)
        logger.debug(
            f"{GIT_KS_STR} registered as the keyserver in {repo_conf_worktree_ks_file}"
        )
        repo_conf_worktree_ks_url_file = Path(repo_conf_worktree, KEYSERVER_URL_F_NAME)
        repo_conf_worktree_ks_url_file.write_text(
            str(SELF_REPO)
        )  # denote that the git keyserver is on the same repo
        logger.debug(
            f"{SELF_REPO} registered as the git keyserver repo path in {repo_conf_worktree_ks_url_file}"
        )
        repo_conf_worktree_git = self.git.git_opts_override(
            C=[repo_conf_worktree]
        )  # get special separate git for the
        # repo conf branch's worktree
        repo_conf_worktree_git.add_subcmd().add(
            str(repo_conf_worktree_ks_file), str(repo_conf_worktree_ks_url_file)
        )
        logger.debug(
            f"`{repo_conf_worktree_ks_file}` and `{repo_conf_worktree_ks_url_file}` added to repo "
            "conf worktree."
        )
        repo_conf_worktree_git.subcmd_unchecked().run(
            ["commit", "-m", "git keyserver registered."]
        )
        logger.info("Central configuration saved.")
        repo_conf_worktree_git.subcmd_unchecked().run(
            ["config", "--local", GIT_KS_KEYSERVER_PATH_KEY, str(SELF_REPO)]
        )
        logger.info("Local configuration saved.")
        logger.debug(f"Storing {GIT_KS_STR} branch configuration in repo conf branch.")
        repo_conf_worktree_ks_branch_file = Path(
            repo_conf_worktree, KEYSERVER_BRANCH_F_NAME
        )
        repo_conf_worktree_ks_branch_file.write_text(keys_base_branch)
        logger.debug(
            f"Noted {keys_base_branch} as keys_base_branch in {repo_conf_worktree_ks_branch_file}"
        )
        repo_conf_worktree_git.add_subcmd().add(str(repo_conf_worktree_ks_branch_file))
        logger.debug(
            f"Indexed {repo_conf_worktree_ks_branch_file} in worktree {repo_conf_worktree}"
        )
        repo_conf_worktree_git.subcmd_unchecked().run(
            ["commit", "-m", "git keyserver base branch"]
        )
        logger.debug(f"Registered {GIT_KS_BRANCH_CONFIG_KEY}={keys_base_branch}")

        logger.success(f"Initialised {GIT_KS_STR}.")
        logger.trace("Exiting")

    def get_or_create_worktree(self, branch_name: str):
        """
        :param branch_name: name of the branch to get or create worktree for.
        :return: the worktree path for an existing worktree for branch ``branch_name`` or creates one if the worktree
            doesn't exist and then returns the path to it.
        """
        logger.trace("Entering")
        logger.debug(f"branch_name: {branch_name}")
        branch_worktree = self.get_existing_worktree(branch_name)
        if not branch_worktree:
            logger.debug("Repo conf branch worktree does not exist.")
            branch_worktree = self.worktree_generator.generate_worktree(
                self.git.root_dir, branch_name
            )
            logger.debug("Created repo conf branch worktree")
        logger.trace("Exiting")
        return branch_worktree

    def get_existing_worktree(self, branch_name: str) -> Path | None:
        """
        Get path to existing worktree for ``branch_name``.

        :param branch_name: branch to query the workspace for.
        :return: Path to the worktree for ``branch_name`` or ``None`` if the said worktree does not exist.
        """
        logger.trace("Entering")
        logger.debug(f"branch_name: {branch_name}")
        worktree_str = self.git.subcmd_unchecked().run(
            ["worktree", "list", "--porcelain", "-z"]
        ).stdout.strip()
        # TODO: send a feature request to git to provide worktree with
        #  either a git worktree list --get <branch-pattern>
        #  or simplt git worktree list <branch-pattern>
        worktree_map = parse_git_worktree_branches_only(worktree_str)
        ref_name = (
            branch_name
            if branch_name.startswith("refs/")
            else f"refs/heads/{branch_name}"
        )
        details = worktree_map.get(branch_name) or worktree_map.get(ref_name)
        if details is None or "worktree" not in details:
            logger.debug(f"worktree for branch {branch_name}: None")
            logger.trace("Exiting")
            return None
        repo_conf_worktree = Path(details["worktree"])
        logger.debug(f"worktree for branch {branch_name}: {repo_conf_worktree}")
        logger.trace("Exiting")
        return repo_conf_worktree

    def worktree_dir_for(self, branch_name: str) -> Path:
        """
        Return the checkout directory for ``branch_name``.

        ``generate_worktree`` returns the parent random directory; an existing
        porcelain listing returns the worktree path itself. This method yields
        the directory that actually contains the branch files.
        """
        logger.trace("Entering")
        logger.debug(f"branch_name: {branch_name}")
        base = self.get_or_create_worktree(branch_name)
        candidate = Path(base, branch_name)
        resolved = candidate if candidate.exists() else Path(base)
        logger.debug(f"worktree_dir_for {branch_name}: {resolved}")
        logger.trace("Exiting")
        return resolved

    def set_local_user_info(self, repo_root: Path | None = None):
        """
        Set user.name and user.email in git repo identified by ``git`` param.

        :param repo_root: operate on supplied repo_root else directly operate on the instance's ``self.git`` repo root.
        """
        logger.trace("Entering")
        logger.debug(f"repo_root: {repo_root}")
        git = self.git
        if repo_root:
            git = git.git_opts_override(C=[repo_root])
            logger.debug(f"Obtained repo_root specific git instance: {git}")

        if self.user_name:
            logger.debug("user.name supplied for setting.")
            git.subcmd_unchecked().run(["config", "--local", "user.name", self.user_name])
            logger.debug(f"Set local git.user.name: {self.user_name}")
            logger.info("Supplied user.name set locally.")
        else:
            logger.info("No user.name supplied for setting. Proceeding with default.")
        if self.user_email:
            logger.debug("user.email supplied for setting.")
            git.subcmd_unchecked().run(
                ["config", "--local", "user.email", self.user_email]
            )
            logger.debug(f"Set local git.user.email: {self.user_email}")
            logger.info("Supplied user.email set locally.")
        else:
            logger.info("No user.email supplied for setting. Proceeding with default.")
        logger.trace("Exiting")

    @overload
    @override
    def clone(
        self, *, url: GitSelf = SELF_REPO, base_dir: GitSelf = SELF_REPO
    ) -> GitKSCloneResult: ...

    @overload
    @override
    def clone(self, *, url: str, base_dir: Path | None = None) -> GitKSCloneResult: ...

    @override
    def clone(
        self,
        *,
        url: str | GitSelf = SELF_REPO,
        base_dir: Path | None | GitSelf = SELF_REPO,
    ) -> GitKSCloneResult:
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
            raise GitKsException(errmsg, exit_code=ERR_INVALID_USAGE) from ValueError(
                errmsg
            )

        if base_dir == SELF_REPO and url != SELF_REPO:
            errmsg = "SELF_REPO base_dir does not allow url configuration."
            logger.error(errmsg)
            raise GitKsException(errmsg, exit_code=ERR_INVALID_USAGE) from ValueError(
                errmsg
            )

        if base_dir == SELF_REPO and url == SELF_REPO:
            message = "No clone needed as repo itself is the keyserver."
            logger.notice(message)
            logger.info("No-op")
            retval = GitKSCloneResult(
                connected=True,
                message=message,
                repo_path=self.repo_root_dir,
                code=200,
                details=dict(status="OK", operation="NOOP"),
            )
        else:
            base_dir = base_dir or self.clone_base_dir
            logger.debug(f"computed base_dir: {base_dir}")
            logger.info("Trying to clone the repo in desired base_dir.")
            repo_name = extract_repo_name(url)
            logger.debug(f"Extracted repo name: {repo_name}")
            repo_dir = Path(base_dir, repo_name)
            logger.debug(f"repo_dir: {repo_dir}")
            if is_git_repo(repo_dir):
                message = f"Repo already cloned at {repo_dir}"
                logger.notice(f"{message}. skipping clone..")
                retval = GitKSCloneResult(
                    connected=True,
                    message=message,
                    repo_path=repo_dir,
                    code=200,
                    details=dict(status="ALREADY_EXISTS", operation="NOOP"),
                )
            else:
                logger.debug(f"Cloning the repo in repo_dir: {repo_dir}")
                clone_cmd = ["git", "clone", str(url), str(repo_dir)]
                logger.debug(f"Running: {clone_cmd}")
                try:
                    completed_process = subprocess.run(
                        clone_cmd, capture_output=True, check=True, text=True
                    )
                    logger.info(f"GitKeyserver repo cloned in: {repo_dir}.")
                    self.set_local_user_info(repo_dir)
                except CalledProcessError as e:
                    logger.error(
                        f"Error `{e}` while cloning repo `{repo_name}` from url `{url}`"
                    )
                    raise GitKsException(
                        f"Error while cloning repo `{repo_name}` from url `{url}`",
                        exit_code=e.returncode,
                        connected=False,
                        message=e.stderr,
                        code=e.returncode,
                        status="CLONE_ERROR",
                        operation="clone",
                        out=e.output,
                        cmd=e.cmd,
                    ) from e
                else:
                    logger.success("GitKeyserver cloned.")
                    retval = GitKSCloneResult(
                        connected=True,
                        message=completed_process.stderr,
                        repo_path=repo_dir,
                        code=completed_process.returncode,
                        details=dict(
                            status="OK", operation="clone", out=completed_process.stdout
                        ),
                    )
        logger.trace("Exiting")
        return retval

    def register(self, url: str) -> KeyServerConnectResult:
        logger.trace("Entering")
        logger.debug(f"url: {url}")
        if url == str(SELF_REPO):
            logger.debug(f"Registering self repo {SELF_REPO}")
            retval = self.clone(url=SELF_REPO)
        else:
            logger.debug(f"Registering a clone at url: {url}")
            retval = self.clone(url=url)
        logger.success(f"{GIT_KS_STR} connected.")
        logger.trace("Exiting")
        return retval

    @override
    def send_key(
        self, public_key: bytes | str, signature: str | None = None
    ) -> KeyUploadResult:
        logger.trace("Entering")
        logger.debug(
            "Starting section of supplied public_key: %.10s", public_key
        )  # not using f-string to make this lazy
        logger.debug("Testing public_key data for validity.")
        self.key_validator.validate_key(public_key)
        logger.info("Supplied public key is valid.")

        show = self.git.subcmd_unchecked().run(
            ["show", f"{REPO_CONF_BRANCH}:{KEYSERVER_BRANCH_F_NAME}"],
            text=True,
        )
        keys_base = show.stdout.strip()
        logger.debug(f"keys_base: {keys_base}")

        requests_branch = f"{keys_base}/{REQUESTS_STR}"
        approved_branch = f"{keys_base}/{APPROVED_STR}"
        logger.debug(f"requests_branch: {requests_branch}")
        requests_wt = self.worktree_dir_for(requests_branch)
        logger.debug(f"requests_wt: {requests_wt}")
        approved_wt = self.worktree_dir_for(approved_branch)
        logger.debug(f"approved_wt: {approved_wt}")

        logger.debug(f"Getting configured {GIT_KS_DIR_CONFIG_KEY}")
        git_ks_dir = self.git.subcmd_unchecked().run(
            ["config", "--local", "--get", GIT_KS_DIR_CONFIG_KEY], text=True
        ).stdout.strip()
        git_ks_dir = Path(git_ks_dir) if git_ks_dir else None
        logger.debug(f"Got Configured {GIT_KS_DIR_CONFIG_KEY}: {git_ks_dir}")
        if not git_ks_dir:
            logger.debug(f"No {GIT_KS_DIR_CONFIG_KEY} configured.")
            git_ks_dir = GIT_KS_DIR
            logger.debug(f"Setting {GIT_KS_DIR_CONFIG_KEY}={GIT_KS_DIR}")
        git_ks_dir = Path(self.repo_root_dir, git_ks_dir)
        logger.debug(f"Full git_ks_dir: {git_ks_dir}")
        requests_gpg_home = Path(git_ks_dir, REQUESTS_STR)
        logger.debug(f"requests_gpg_home: {requests_gpg_home}")

        key_id = self.get_key_name_from_key_data(public_key)
        logger.debug(f"formulated key_id: {key_id}")
        key_file = requests_wt / f"{key_id}.asc"
        approved_key_file = approved_wt / f"{key_id}.asc"
        if key_file.exists() or approved_key_file.exists():
            message = f"Key {key_id} already exists in requests or approved."
            logger.notice(message)
            logger.trace("Exiting")
            return KeyUploadResult(
                status=KeyUploadStatus.ALREADY_EXISTS,
                message=message,
                server_id=key_id,
            )

        key_text = (
            public_key.decode("utf-8") if isinstance(public_key, bytes) else public_key
        )
        if signature is None:
            signature = make_detached_signature(key_text, requests_gpg_home)
        sig_file = requests_wt / f"{key_id}.asc.sig"

        requests_git = self.git.git_opts_override(C=[requests_wt]).git_envs_override(
            GNUPGHOME=str(requests_gpg_home)
        )
        logger.debug("Got git instance for requests worktree.")

        key_user_name = self.get_key_user_name(key_text)
        logger.debug(f"key_user_name: {key_user_name}")
        key_user_email = self.get_key_user_email(key_text)
        logger.debug(f"key_user_email: {key_user_email}")

        key_file.write_text(key_text, encoding="utf-8")
        logger.debug("Written key data %.10s to key_file: %s", key_text, key_file)
        sig_file.write_text(signature, encoding="utf-8")
        logger.debug(f"Written detached signature to {sig_file}")

        indexed = [
            self.index_user_name(requests_wt, key_user_name, key_id),
            self.index_user_email(requests_wt, key_user_email, key_id),
        ]
        logger.info("Indexed user name and email.")

        to_add = [str(key_file), str(sig_file), *[str(p) for p in indexed if p]]
        requests_git.add_subcmd().add(*to_add)
        logger.debug("Indexed key and signature files.")

        commit_runcmd = [
            "commit",
            "-m",
            key_id,
            "-m",
            f"Request key {key_id} for user {key_user_name}",
        ]
        logger.debug(f"Running commit command: {commit_runcmd}")
        requests_git.subcmd_unchecked().run(commit_runcmd)
        logger.info("Saved key request in local db.")

        remotes = self.git.subcmd_unchecked().run(["remote"], text=True).stdout.strip()
        if remotes:
            requests_git.subcmd_unchecked().run(["push"])
            logger.info("Pushed to remote server.")
        else:
            logger.info("No git remote configured; skipping push.")

        commit_hash = requests_git.subcmd_unchecked().run(
            ["rev-parse", "HEAD"], text=True
        ).stdout.strip()
        logger.success("Successfully queued the key request.")
        logger.trace("Exiting")
        return KeyUploadResult(
            status=KeyUploadStatus.PENDING,
            message=f"Key {key_id} queued in requests",
            server_id=commit_hash,
        )

    def get_key_name_from_key_data(self, public_key: bytes | str) -> str:
        """Fingerprint used as the key filename stem. Delegates to ``gpg.py``."""
        return gpg_get_key_name_from_key_data(public_key)

    def get_key_user_name(self, public_key: bytes | str) -> str:
        """Primary uid name. Delegates to ``gpg.py``."""
        return gpg_get_key_user_name(public_key)

    def get_key_user_email(self, public_key: bytes | str) -> str:
        """Primary uid email. Delegates to ``gpg.py``."""
        return gpg_get_key_user_email(public_key)

    def index_user_name(
        self, worktree: Path, user_name: str, key_id: str
    ) -> Path | None:
        """Index ``key_id`` by user display name. Delegates to ``utils.py``."""
        return index_user_name(worktree, user_name, key_id)

    def index_user_email(
        self, worktree: Path, user_email: str, key_id: str
    ) -> Path | None:
        """Index ``key_id`` by email (not by name). Delegates to ``utils.py``."""
        return index_user_email(worktree, user_email, key_id)

    def _read_keys_base(self) -> str:
        show = self.git.subcmd_unchecked().run(
            ["show", f"{REPO_CONF_BRANCH}:{KEYSERVER_BRANCH_F_NAME}"],
            text=True,
        )
        return show.stdout.strip()

    def _resolved_git_ks_dir(self) -> Path:
        git_ks_dir = self.git.subcmd_unchecked().run(
            ["config", "--local", "--get", GIT_KS_DIR_CONFIG_KEY], text=True
        ).stdout.strip()
        configured = Path(git_ks_dir) if git_ks_dir else GIT_KS_DIR
        return Path(self.repo_root_dir, configured)

    def _permission_layout(self) -> tuple[Path, Path, Path, Path, Path]:
        """
        :return: requests worktree, approved worktree, denied worktree,
            requests GPG home, owner (approved) GPG home.
        """
        keys_base = self._read_keys_base()
        git_ks_dir = self._resolved_git_ks_dir()
        requests_wt = self.worktree_dir_for(f"{keys_base}/{REQUESTS_STR}")
        approved_wt = self.worktree_dir_for(f"{keys_base}/{APPROVED_STR}")
        denied_wt = self.worktree_dir_for(f"{keys_base}/{DENIED_STR}")
        return (
            requests_wt,
            approved_wt,
            denied_wt,
            Path(git_ks_dir, REQUESTS_STR),
            Path(git_ks_dir, APPROVED_STR),
        )

    def _git_for_worktree(self, worktree: Path, gnupghome: Path):
        return self.git.git_opts_override(C=[worktree]).git_envs_override(
            GNUPGHOME=str(gnupghome)
        )

    def _maybe_push(self, worktree_git) -> None:
        remotes = self.git.subcmd_unchecked().run(["remote"], text=True).stdout.strip()
        if remotes:
            worktree_git.subcmd_unchecked().run(["push"])
            logger.info("Pushed to remote server.")
        else:
            logger.info("No git remote configured; skipping push.")

    def _head_hash(self, worktree_git) -> str:
        return worktree_git.subcmd_unchecked().run(
            ["rev-parse", "HEAD"], text=True
        ).stdout.strip()

    def _load_pending_files(self, requests_wt: Path, key_id: str) -> PendingKey | None:
        key_file = requests_wt / f"{key_id}.asc"
        sig_file = requests_wt / f"{key_id}.asc.sig"
        if not key_file.is_file() or not sig_file.is_file():
            return None
        return PendingKey(
            key_id=key_id,
            public_key=key_file.read_text(encoding="utf-8"),
            requester_signature=sig_file.read_text(encoding="utf-8"),
        )

    def _remove_pending_from_requests(
        self, requests_wt: Path, requests_git, key_id: str
    ) -> None:
        to_remove = [
            requests_wt / f"{key_id}.asc",
            requests_wt / f"{key_id}.asc.sig",
        ]
        for root in (
            requests_wt / "index" / "names",
            requests_wt / "index" / "emails",
        ):
            if not root.is_dir():
                continue
            for path in root.iterdir():
                if path.is_file() and path.read_text(encoding="utf-8").strip() == key_id:
                    to_remove.append(path)
        existing = [str(p) for p in to_remove if p.exists()]
        if existing:
            requests_git.subcmd_unchecked().run(["rm", "-f", "--", *existing])

    @override
    def list_pending_keys(self) -> list[PendingKey]:
        logger.trace("Entering")
        requests_wt, *_rest = self._permission_layout()
        pending: list[PendingKey] = []
        for key_file in sorted(requests_wt.glob("*.asc")):
            key_id = key_file.stem
            loaded = self._load_pending_files(requests_wt, key_id)
            if loaded:
                pending.append(loaded)
        logger.debug(f"pending count: {len(pending)}")
        logger.trace("Exiting")
        return pending

    @override
    def approve_key(self, key_id: str) -> KeyReviewResult:
        logger.trace("Entering")
        logger.debug(f"key_id: {key_id}")
        requests_wt, approved_wt, _denied_wt, requests_home, owner_home = (
            self._permission_layout()
        )
        pending = self._load_pending_files(requests_wt, key_id)
        if pending is None:
            message = f"Key {key_id} is not pending in requests."
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.NOT_FOUND, key_id=key_id, message=message
            )

        if not verify_detached_signature(
            pending.public_key, pending.requester_signature, requests_home
        ):
            message = f"Requester signature for key {key_id} is invalid."
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.INVALID_SIGNATURE,
                key_id=key_id,
                message=message,
            )

        owner_key_id = first_secret_key_id(owner_home)
        if not owner_key_id:
            message = (
                f"No owner secret key in approved GPG home {owner_home}. "
                "Cannot attest approval."
            )
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.ERROR, key_id=key_id, message=message
            )

        try:
            owner_sig = owner_sign_data(
                pending.public_key, owner_home, owner_key_id
            )
        except ValueError as e:
            logger.error(str(e))
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.ERROR, key_id=key_id, message=str(e)
            )

        approved_git = self._git_for_worktree(approved_wt, owner_home)
        dest_key = approved_wt / f"{key_id}.asc"
        dest_req_sig = approved_wt / f"{key_id}.asc.sig"
        dest_owner_sig = approved_wt / f"{key_id}.owner.sig"
        dest_key.write_text(pending.public_key, encoding="utf-8")
        dest_req_sig.write_text(pending.requester_signature, encoding="utf-8")
        dest_owner_sig.write_text(owner_sig, encoding="utf-8")
        approved_git.add_subcmd().add(
            str(dest_key), str(dest_req_sig), str(dest_owner_sig)
        )
        approved_git.subcmd_unchecked().run(
            [
                "commit",
                "-m",
                key_id,
                "-m",
                f"Approve key {key_id}",
            ]
        )
        self._maybe_push(approved_git)
        commit_hash = self._head_hash(approved_git)

        requests_git = self._git_for_worktree(requests_wt, requests_home)
        self._remove_pending_from_requests(requests_wt, requests_git, key_id)
        requests_git.subcmd_unchecked().run(
            ["commit", "-m", f"Remove approved key {key_id} from requests"]
        )
        self._maybe_push(requests_git)

        logger.success(f"Approved key {key_id}.")
        logger.trace("Exiting")
        return KeyReviewResult(
            status=KeyReviewStatus.APPROVED,
            key_id=key_id,
            message=f"Key {key_id} approved",
            server_id=commit_hash,
        )

    @override
    def deny_key(self, key_id: str, reason: str) -> KeyReviewResult:
        logger.trace("Entering")
        logger.debug(f"key_id: {key_id}")
        logger.debug(f"reason: {reason}")
        requests_wt, _approved_wt, denied_wt, requests_home, owner_home = (
            self._permission_layout()
        )
        pending = self._load_pending_files(requests_wt, key_id)
        if pending is None:
            message = f"Key {key_id} is not pending in requests."
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.NOT_FOUND, key_id=key_id, message=message
            )

        if not verify_detached_signature(
            pending.public_key, pending.requester_signature, requests_home
        ):
            message = f"Requester signature for key {key_id} is invalid."
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.INVALID_SIGNATURE,
                key_id=key_id,
                message=message,
            )

        owner_key_id = first_secret_key_id(owner_home)
        if not owner_key_id:
            message = (
                f"No owner secret key in approved GPG home {owner_home}. "
                "Cannot attest denial."
            )
            logger.error(message)
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.ERROR, key_id=key_id, message=message
            )

        try:
            owner_sig = owner_sign_data(
                pending.public_key, owner_home, owner_key_id
            )
        except ValueError as e:
            logger.error(str(e))
            logger.trace("Exiting")
            return KeyReviewResult(
                status=KeyReviewStatus.ERROR, key_id=key_id, message=str(e)
            )

        denied_git = self._git_for_worktree(denied_wt, owner_home)
        dest_key = denied_wt / f"{key_id}.asc"
        dest_req_sig = denied_wt / f"{key_id}.asc.sig"
        dest_owner_sig = denied_wt / f"{key_id}.owner.sig"
        dest_reason = denied_wt / f"{key_id}.reason.txt"
        dest_key.write_text(pending.public_key, encoding="utf-8")
        dest_req_sig.write_text(pending.requester_signature, encoding="utf-8")
        dest_owner_sig.write_text(owner_sig, encoding="utf-8")
        dest_reason.write_text(reason, encoding="utf-8")
        denied_git.add_subcmd().add(
            str(dest_key),
            str(dest_req_sig),
            str(dest_owner_sig),
            str(dest_reason),
        )
        denied_git.subcmd_unchecked().run(
            [
                "commit",
                "-m",
                key_id,
                "-m",
                f"Deny key {key_id}: {reason}",
            ]
        )
        self._maybe_push(denied_git)
        commit_hash = self._head_hash(denied_git)

        requests_git = self._git_for_worktree(requests_wt, requests_home)
        self._remove_pending_from_requests(requests_wt, requests_git, key_id)
        requests_git.subcmd_unchecked().run(
            ["commit", "-m", f"Remove denied key {key_id} from requests"]
        )
        self._maybe_push(requests_git)

        logger.success(f"Denied key {key_id}.")
        logger.trace("Exiting")
        return KeyReviewResult(
            status=KeyReviewStatus.DENIED,
            key_id=key_id,
            message=f"Key {key_id} denied",
            server_id=commit_hash,
            reason=reason,
        )

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
    entries = data.split(b"\0")

    current = {}
    for entry in entries:
        if not entry:
            # End of a worktree block
            branch = current.get("branch")
            if branch:
                worktrees[branch] = current
            current = {}
            continue

        if b" " in entry:
            key, value = entry.split(b" ", 1)
            current[key.decode()] = value.decode()
        else:
            current[entry.decode()] = True  # flag like 'prunable' or 'locked'

    return worktrees
