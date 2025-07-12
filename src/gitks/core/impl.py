#!/usr/bin/env python3
# coding=utf-8

"""
implementations related to keyserver workings for ``gitks``.
"""
import logging
from pathlib import Path
from typing import override

from gitbolt.git_subprocess.impl.simple import SimpleGitCommand
from logician.configurators.env import VTEnvListLC
from logician.std_log.configurator import StdLoggerConfigurator
from vt.utils.commons.commons.op import RootDirOp
from vt.utils.errors.error_specs import ERR_CMD_NOT_FOUND, ERR_STATE_ALREADY_EXISTS

from gitks.core.model import KeyDeleteResult, KeyData, KeyUploadResult
from gitks.core.base import GitKeyServer, KeyValidator
from gitks.core.errors import GitKsException
from gitks.core.constants import GIT_KS_DIR, GIT_KS_KEYS_BASE_BRANCH, TEST_STR, FINAL_STR, GIT_KS_BRANCH_CONFIG_KEY, \
    GIT_KS_DIR_CONFIG_KEY, KEYSERVER_CONFIG_KEY, GIT_KS_STR

_base_logger = logging.getLogger(__name__)
logger = VTEnvListLC(['GITKS_LOG'], StdLoggerConfigurator()).configure(_base_logger)


class GitKeyServerImpl(GitKeyServer, RootDirOp):

    def __init__(self, key_validator: KeyValidator, repo_root_dir: Path | None = None,
                 user_name: str | None = None,
                 user_email: str | None = None,
                 lenient: bool = True):
        logger.trace('Entering')
        self._key_validator = key_validator
        logger.debug(f"key_validator: {key_validator}")
        logger.debug(f"Supplied repo_root_dir: {repo_root_dir}")
        self.repo_root_dir = repo_root_dir or Path.cwd()
        logger.debug(f"computed repo_root_dir: {repo_root_dir}")
        self.lenient = lenient
        logger.debug(f"lenient: {lenient}")
        logger.trace("Exiting")
        self.git = SimpleGitCommand(self.repo_root_dir)
        if user_name:  # else autodetect
            self.user_name = user_name
            self.git = self.git.git_envs_override(GIT_AUTHOR_NAME=user_name).git_envs_override(
                GIT_COMMITTER_NAME=user_name)
        if user_email:  # else autodetect
            self.user_email = user_email
            self.git = self.git.git_envs_override(GIT_AUTHOR_EMAIL=user_email).git_envs_override(
                GIT_COMMITTER_EMAIL=user_email)

    @override
    def init(self, git_ks_dir: Path = GIT_KS_DIR, keys_base_branch: str = GIT_KS_KEYS_BASE_BRANCH) -> None:
        logger.trace("Entering")
        logger.debug(f"git_ks_dir: {git_ks_dir}")
        logger.debug(f"key_base_branch: {keys_base_branch}")

        logger.info(f"Initialising git repo in {self.root_dir}")
        self.git.subcmd_unchecked.run(['init'])
        logger.debug('repo initialised.')

        logger.debug("Checking if supplied branch exists already.")
        existing_branches = self.git.subcmd_unchecked.run(['branch', '--list', keys_base_branch],
                                                          text=True).stdout.split()
        if keys_base_branch in existing_branches:
            errmsg = f'Requested branch {keys_base_branch} already exists. Rerun with a different branch name.'
            logger.error(errmsg)
            raise GitKsException(errmsg, exit_code=ERR_STATE_ALREADY_EXISTS)

        logger.debug(f"Attempting to create branch {keys_base_branch}")
        main_branches = self.git.subcmd_unchecked.run(['branch', '--list', 'main', 'master'],
                                                      text=True).stdout.split()
        if not main_branches:
            errmsg = "No base main branches (as 'main' or 'master') found."
            logger.notice(errmsg)
            if not self.lenient:
                errmsg += " Lenient mode off."
                logger.error(errmsg)
                raise GitKsException(errmsg, exit_code=ERR_CMD_NOT_FOUND)
            else:
                if self.user_name:
                    self.git.subcmd_unchecked.run(['config', '--local', 'user.name', self.user_name])
                    logger.debug(f"Set local git.user.name: {self.user_name}")
                if self.user_email:
                    self.git.subcmd_unchecked.run(['config', '--local', 'user.email', self.user_email])
                    logger.debug(f"Set local git.user.email: {self.user_email}")

                self.git.subcmd_unchecked.run(['commit', '-m', 'initial commit', '--allow-empty'])
                logger.debug("Empty commit created on main branch.")

        self.git.subcmd_unchecked.run(['branch', keys_base_branch], text=True)
        if keys_base_branch != GIT_KS_KEYS_BASE_BRANCH:
            logger.debug('Different branch name supplied for storing keys.')
            self.git.subcmd_unchecked.run(['config', '--local', GIT_KS_BRANCH_CONFIG_KEY, keys_base_branch])
            logger.debug(f'Registered {GIT_KS_BRANCH_CONFIG_KEY}={keys_base_branch}')
        logger.info(f'key base branch {keys_base_branch} created.')

        git_ks_test_dir = Path(self.root_dir, git_ks_dir, TEST_STR)
        logger.debug(f"attempting to create test directory: {git_ks_test_dir}")
        git_ks_test_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_test_dir} created.")
        git_ks_final_dir = Path(self.root_dir, git_ks_dir, FINAL_STR)
        logger.debug(f"attempting to create final directory: {git_ks_final_dir}")
        git_ks_final_dir.mkdir(parents=True)
        logger.info(f"Directory {git_ks_final_dir} created.")
        if git_ks_dir != GIT_KS_DIR:
            logger.debug('Different gitks directory supplied for storing keys.')
            self.git.subcmd_unchecked.run(['config', '--local', GIT_KS_DIR_CONFIG_KEY, str(git_ks_dir)])
            logger.debug(f'Registered {GIT_KS_DIR_CONFIG_KEY}={str(git_ks_dir)}')

        self.git.subcmd_unchecked.run(['config', '--local', KEYSERVER_CONFIG_KEY, GIT_KS_STR])
        logger.info(f"Registered 'gitks' as the {KEYSERVER_CONFIG_KEY}")

        logger.success('Initialised gitks.')
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
