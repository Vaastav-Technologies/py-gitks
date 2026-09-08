#!/usr/bin/env python3

"""Command-line entry for ``gitks``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pprint import pp

import gnupg
from gitbolt import get_git

from gitks.core.base import GitKeyServer, GitKeyServerClient
from gitks.core.constants import DEFAULT_KEY_VALIDATOR
from gitks.core.factory import git_key_server, git_key_server_client
from gitks.core.model import GitKSCloneResult


def cmd_init(
    repo_dir: str,
    user_name: str | None = None,
    user_email: str | None = None,
    validator: str = DEFAULT_KEY_VALIDATOR,
    *,
    key_server: GitKeyServer | None = None,
) -> int:
    repo = Path(repo_dir).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    ks: GitKeyServer = key_server or git_key_server(
        repo,
        user_name=user_name,
        user_email=user_email,
    )
    ks.init(validator=validator)
    print(f"Initialised gitks repo in {ks.root_dir}")
    return 0


def cmd_clone(
    url: str,
    dest_dir: str | None = None,
    *,
    key_server_client: GitKeyServerClient | None = None,
) -> int:
    dest_parent = Path(dest_dir).resolve() if dest_dir else Path.cwd()
    ks: GitKeyServerClient = key_server_client or git_key_server_client(
        Path.cwd(),
        clone_base_dir=dest_parent,
        worktrees_parent=dest_parent,
    )
    result: GitKSCloneResult = ks.clone(url=url, base_dir=dest_parent)
    print(result.message)
    if result.repo_path:
        print(str(result.repo_path))
    return 0 if result.connected else 1


def cmd_list_keys(args: list[str] | None = None) -> int:
    """List GPG keys and git version (key-validation branch)."""
    if args is None:
        args = []
    print(args)
    gpg = gnupg.GPG()
    pp(gpg.list_keys())
    git = get_git()
    print(git.version)
    return 0


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
    init_p.add_argument(
        "--validator",
        default=DEFAULT_KEY_VALIDATOR,
        help=f"Key validator to register (default: {DEFAULT_KEY_VALIDATOR}).",
    )

    clone_p = sub.add_parser("clone", help="Clone a gitks repo.")
    clone_p.add_argument("url", help="Git URL or path of the gitks repo.")
    clone_p.add_argument(
        "--dir",
        default=None,
        help="Parent directory to clone into (default: cwd).",
    )

    sub.add_parser("list-keys", help="List GPG keys and print git version.")

    return parser


def main_cli(args: list[str] | None = None) -> int:
    parser = build_parser()
    args = args if args else sys.argv[1:]
    ns = parser.parse_args(args)
    if ns.command == "init":
        return cmd_init(ns.dir, ns.user_name, ns.user_email, ns.validator)
    if ns.command == "clone":
        return cmd_clone(ns.url, ns.dir)
    if ns.command == "list-keys":
        return cmd_list_keys(args[1:])
    parser.error(f"unknown command {ns.command}")


if __name__ == "__main__":
    main_cli()
