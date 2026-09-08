#!/usr/bin/env python3
# coding=utf-8

"""
utility methods related to ``gitks``.
"""

import os
from urllib.parse import urlparse
from pathlib import Path
import subprocess


def extract_repo_name(repo_url: str) -> str:
    """
    Extract the repository name from a Git URL or local path.

    >>> extract_repo_name('https://github.com/user/my-repo.git')
    'my-repo'
    >>> extract_repo_name('git@github.com:user/my-repo.git')
    'my-repo'
    >>> extract_repo_name('/home/user/code/my-local-repo')
    'my-local-repo'
    >>> extract_repo_name('../relative/path/to/repo.git')
    'repo'
    >>> extract_repo_name('https://myserver.com/repo.git?token=abc123')
    'repo'
    """
    # Handle both URLs and file paths
    path = urlparse(repo_url).path if "://" in repo_url else repo_url
    repo_name = os.path.basename(path)
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return repo_name


def is_git_repo(path: Path) -> bool:
    """
    Check if a directory is a valid Git repository.

    >>> import tempfile, os
    >>> with tempfile.TemporaryDirectory() as temp:
    ...     tmp = Path(temp)
    ...     _ = subprocess.run(['git', 'init'], cwd=tmp, stdout=subprocess.DEVNULL)
    ...     is_git_repo(tmp)
    True
    >>> is_git_repo(Path("/tmp"))  # Assuming /tmp is not a git repo
    False
    """
    if not path.exists():
        return False
    if not path.is_dir():
        return False
    try:
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def index_filename(value: str) -> str:
    """
    Safe single path segment for name/email index files.

    >>> index_filename('Alice Example')
    'Alice_Example'
    >>> index_filename('alice@example.com')
    'alice@example.com'
    """
    return "".join(c if c.isalnum() or c in "._@+-" else "_" for c in value)


def index_user_name(worktree: Path, user_name: str, key_id: str) -> Path | None:
    """
    Write ``key_id`` under ``worktree/index/names/`` keyed by ``user_name``.

    :return: path written, or ``None`` if ``user_name`` is empty.
    """
    if not user_name:
        return None
    path = worktree / "index" / "names" / index_filename(user_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key_id, encoding="utf-8")
    return path


def index_user_email(worktree: Path, user_email: str, key_id: str) -> Path | None:
    """
    Write ``key_id`` under ``worktree/index/emails/`` keyed by ``user_email``.

    Must be called with the email, not the display name.
    """
    if not user_email:
        return None
    path = worktree / "index" / "emails" / index_filename(user_email)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key_id, encoding="utf-8")
    return path
