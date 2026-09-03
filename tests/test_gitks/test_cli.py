#!/usr/bin/env python3

"""CLI argparse for gitks."""

import pytest

from gitks.cli.__main__ import build_parser


def test_cli_help_lists_init_and_clone():
    text = build_parser().format_help()
    assert "init" in text
    assert "clone" in text


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_cli_init_args():
    ns = build_parser().parse_args(
        [
            "init",
            "--dir",
            "repo",
            "--user-name",
            "cli",
            "--user-email",
            "cli@example.test",
        ]
    )
    assert ns.command == "init"
    assert ns.dir == "repo"
    assert ns.user_name == "cli"
    assert ns.user_email == "cli@example.test"


def test_cli_clone_args():
    ns = build_parser().parse_args(
        ["clone", "https://example.test/ks.git", "--dir", "parent"]
    )
    assert ns.command == "clone"
    assert ns.url == "https://example.test/ks.git"
    assert ns.dir == "parent"
