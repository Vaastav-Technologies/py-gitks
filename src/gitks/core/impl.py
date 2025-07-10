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

from gitks.core import KeyDeleteResult, KeyData, KeyValidator, KeyUploadResult
from gitks.core.base import GitKeyServer
from gitks.core.constants import GIT_KS_DIR, GIT_KS_KEYS_BRANCH

_base_logger = logging.getLogger(__name__)
logger = VTEnvListLC(['GITKS_LOG'], StdLoggerConfigurator()).configure(_base_logger)


class GitKeyServerImpl(GitKeyServer, RootDirOp):

    def __init__(self, key_validator: KeyValidator, repo_root_dir: Path | None = None, lenient: bool = True):
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

    @override
    def init(self, git_ks_dir: Path = GIT_KS_DIR, branch: str = GIT_KS_KEYS_BRANCH) -> None:
        logger.trace("Entering")
        logger.debug(f"git_ks_dir: {git_ks_dir}")
        logger.debug(f"branch: {branch}")

        logger.info(f"Initialising git repo in {self.root_dir}")
        self.git.subcmd_unchecked.run(['init'])
        logger.info('repo initialised.')

        logger.debug(f"attempting to create branch {branch}")
        self.git.subcmd_unchecked.run(['branch', branch])
        logger.debug('branch created.')

        git_ks_dir = Path(self.root_dir, git_ks_dir)
        logger.debug(f"attempting to create directory: {git_ks_dir}")
        git_ks_dir.mkdir(parents=True)
        logger.debug(f"Directory {git_ks_dir} created.")
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
