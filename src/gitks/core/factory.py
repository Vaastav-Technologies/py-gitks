#!/usr/bin/env python3

"""
Construct ``gitks`` objects behind ``GitKeyServer`` / ``GitKeyServerClient``.

Callers (CLI, tests, library users) should depend on those interfaces.
``WorkTreeGitKeyServerImpl`` is the default implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gitks.core.base import GitKeyServer, GitKeyServerClient, KeyValidator
from gitks.core.constants import GITKS_WORKTREES_DIR_STR
from gitks.core.gpg import GpgKeyValidator
from gitks.core.importing import KeyImporter

if TYPE_CHECKING:
    from gitks.core.impl import WorkTreeGenerator, WorkTreeGitKeyServerImpl


def worktrees_dir(parent: Path) -> Path:
    """Directory that holds generated gitks worktrees for ``parent``."""
    return Path(parent).resolve() / GITKS_WORKTREES_DIR_STR


def _build_worktree_gitks(
    repo_root_dir: Path,
    *,
    user_name: str | None = None,
    user_email: str | None = None,
    worktree_generator: WorkTreeGenerator | None = None,
    worktrees_parent: Path | None = None,
    clone_base_dir: Path | None = None,
    key_validator: KeyValidator | None = None,
    key_importer: KeyImporter | None = None,
) -> WorkTreeGitKeyServerImpl:
    from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl

    generator = worktree_generator or BaseDirWorkTreeGenerator(
        worktrees_dir(worktrees_parent or Path(repo_root_dir).parent)
    )
    return WorkTreeGitKeyServerImpl(
        key_validator or GpgKeyValidator(),
        Path(repo_root_dir),
        user_name=user_name,
        user_email=user_email,
        worktree_generator=generator,
        clone_base_dir=clone_base_dir,
        key_importer=key_importer,
    )


def git_key_server(
    repo_root_dir: Path,
    *,
    user_name: str | None = None,
    user_email: str | None = None,
    worktree_generator: WorkTreeGenerator | None = None,
    worktrees_parent: Path | None = None,
    clone_base_dir: Path | None = None,
    key_validator: KeyValidator | None = None,
    key_importer: KeyImporter | None = None,
) -> GitKeyServer:
    """
    Default ``GitKeyServer`` (worktree-backed).

    Use this for ``init``. The concrete class also implements the client
    interface; prefer ``git_key_server_client`` when calling ``clone``.
    """
    return _build_worktree_gitks(
        repo_root_dir,
        user_name=user_name,
        user_email=user_email,
        worktree_generator=worktree_generator,
        worktrees_parent=worktrees_parent,
        clone_base_dir=clone_base_dir,
        key_validator=key_validator,
        key_importer=key_importer,
    )


def git_key_server_client(
    repo_root_dir: Path,
    *,
    user_name: str | None = None,
    user_email: str | None = None,
    worktree_generator: WorkTreeGenerator | None = None,
    worktrees_parent: Path | None = None,
    clone_base_dir: Path | None = None,
    key_validator: KeyValidator | None = None,
    key_importer: KeyImporter | None = None,
) -> GitKeyServerClient:
    """
    Default ``GitKeyServerClient`` (worktree-backed).

    Use this for ``clone`` and key send/receive/search/publish operations.
    """
    return _build_worktree_gitks(
        repo_root_dir,
        user_name=user_name,
        user_email=user_email,
        worktree_generator=worktree_generator,
        worktrees_parent=worktrees_parent,
        clone_base_dir=clone_base_dir,
        key_validator=key_validator,
        key_importer=key_importer,
    )
