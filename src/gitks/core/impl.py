#!/usr/bin/env python3
# coding=utf-8

"""
implementations related to keyserver workings for ``gitks``.
"""
import logging
import subprocess
from pathlib import Path
from subprocess import CalledProcessError

from gitbolt.git_subprocess.exceptions import GitCmdException
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

    def init(self, git_ks_dir: Path = GIT_KS_DIR, branch: str = GIT_KS_KEYS_BRANCH) -> None:
        logger.trace("Entering")
        logger.debug(f"git_ks_dir: {git_ks_dir}")
        logger.debug(f"branch: {branch}")

        logger.info(f"Initialising git repo in {self.root_dir}")
        try:
            subprocess.run(['git', 'init', str(self.root_dir)], check=True, capture_output=True, text=True)
        except CalledProcessError as e:
            logger.error(f"Error while initialising repo at {self.root_dir}")
            raise GitCmdException('Error while initialising repo', called_process_error=e) from e
        logger.info('repo initialised.')

        logger.debug(f"attempting to create branch {branch}")
        try:
            subprocess.run(['git', 'branch', branch], check=True, capture_output=True, text=True)
        except CalledProcessError as e:
            logger.error(f"Error while creating branch {branch}")
            raise GitCmdException('Error while creating branch', called_process_error=e) from e
        logger.debug('branch created.')

        git_ks_dir = Path(self.root_dir, git_ks_dir)
        logger.debug(f"attempting to create directory: {git_ks_dir}")
        git_ks_dir.mkdir(parents=True)
        logger.debug(f"Directory {git_ks_dir} created.")
        logger.trace("Exiting")

    def send_key(self, public_key: bytes | str) -> KeyUploadResult:
        pass

    def receive_key(self, key_id: str) -> bytes | str:
        pass

    def search_keys(self, key_search_str: str) -> list[KeyData]:
        pass

    def delete_key(self, key_id: str) -> KeyDeleteResult:
        pass

    @property
    def root_dir(self) -> Path:
        return self.repo_root_dir

    @property
    def key_validator(self) -> KeyValidator:
        return self._key_validator
