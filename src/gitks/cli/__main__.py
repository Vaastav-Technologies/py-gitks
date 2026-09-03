#!/usr/bin/env python3

"""Command-line entry for ``gitks``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gitks.core.constants import GITKS_WORKTREES_DIR_STR
from gitks.core.gpg import GpgKeyValidator
from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl
from gitks.core.model import GitKSCloneResult


def _worktrees_dir(parent: Path) -> Path:
    return Path(parent).resolve() / GITKS_WORKTREES_DIR_STR


def cmd_init(
    repo_dir: str,
    user_name: str | None = None,
    user_email: str | None = None,
) -> int:
    repo = Path(repo_dir).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    ks = WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        repo,
        user_name=user_name,
        user_email=user_email,
        worktree_generator=BaseDirWorkTreeGenerator(_worktrees_dir(repo.parent)),
    )
    ks.init()
    print(f"Initialised gitks repo in {repo}")
    return 0


def cmd_clone(url: str, dest_dir: str | None = None) -> int:
    dest_parent = Path(dest_dir).resolve() if dest_dir else Path.cwd()
    ks = WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        Path.cwd(),
        clone_base_dir=dest_parent,
        worktree_generator=BaseDirWorkTreeGenerator(_worktrees_dir(dest_parent)),
    )
    result: GitKSCloneResult = ks.clone(url=url, base_dir=dest_parent)
    print(result.message)
    if result.repo_path:
        print(str(result.repo_path))
    return 0 if result.connected else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitks",
        description="Git-backed GPG keyserver.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialise a gitks repo.")
    init_p.add_argument(
        "--dir",
        default=".",
        help="Directory to initialise (default: current directory).",
    )
    init_p.add_argument("--user-name", default=None, help="git user.name")
    init_p.add_argument("--user-email", default=None, help="git user.email")

    clone_p = sub.add_parser("clone", help="Clone a gitks repo.")
    clone_p.add_argument("url", help="Git URL or path of the gitks repo.")
    clone_p.add_argument(
        "--dir",
        default=None,
        help="Parent directory to clone into (default: cwd).",
    )

    return parser


def main_cli(args: list[str] | None = None) -> int:
    parser = build_parser()
    args = args if args else sys.argv[1:]
    ns = parser.parse_args(args)
    if ns.command == "init":
        return cmd_init(ns.dir, ns.user_name, ns.user_email)
    if ns.command == "clone":
        return cmd_clone(ns.url, ns.dir)
    parser.error(f"unknown command {ns.command}")


if __name__ == "__main__":
    main_cli()
