#!/usr/bin/env python3
# coding=utf-8

"""Command-line entry for ``gitks``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gitks.core.gpg import GpgKeyValidator
from gitks.core.impl import BaseDirWorkTreeGenerator, WorkTreeGitKeyServerImpl
from gitks.core.model import GitKSCloneResult


def _ks(repo: Path) -> WorkTreeGitKeyServerImpl:
    worktrees = Path(repo).resolve().parent / ".gitks-worktrees"
    return WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        Path(repo).resolve(),
        worktree_generator=BaseDirWorkTreeGenerator(worktrees),
    )


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.dir).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    ks = WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        repo,
        user_name=args.user_name,
        user_email=args.user_email,
        worktree_generator=BaseDirWorkTreeGenerator(repo.parent / ".gitks-worktrees"),
    )
    ks.init()
    print(f"Initialised gitks repo in {repo}")
    return 0


def cmd_clone(args: argparse.Namespace) -> int:
    dest_parent = Path(args.dir).resolve() if args.dir else Path.cwd()
    ks = WorkTreeGitKeyServerImpl(
        GpgKeyValidator(),
        Path.cwd(),
        clone_base_dir=dest_parent,
        worktree_generator=BaseDirWorkTreeGenerator(dest_parent / ".gitks-worktrees"),
    )
    result: GitKSCloneResult = ks.clone(url=args.url, base_dir=dest_parent)
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
    init_p.set_defaults(func=cmd_init)

    clone_p = sub.add_parser("clone", help="Clone a gitks repo.")
    clone_p.add_argument("url", help="Git URL or path of the gitks repo.")
    clone_p.add_argument(
        "--dir",
        default=None,
        help="Parent directory to clone into (default: cwd).",
    )
    clone_p.set_defaults(func=cmd_clone)

    return parser


def main_cli(args: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(args if args is not None else sys.argv[1:])
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main_cli())
