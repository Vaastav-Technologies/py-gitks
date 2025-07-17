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
            ['git', '-C', str(path), 'rev-parse', '--is-inside-work-tree'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
