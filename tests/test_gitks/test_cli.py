#!/usr/bin/env python3
# coding=utf-8

"""CLI subcommands for gitks."""

import pytest

from gitks.cli.__main__ import build_parser, main_cli


def test_cli_help_lists_init_and_clone():
    text = build_parser().format_help()
    assert "init" in text
    assert "clone" in text


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_cli_init(tmp_path):
    code = main_cli(
        [
            "init",
            "--dir",
            str(tmp_path),
            "--user-name",
            "cli",
            "--user-email",
            "cli@example.test",
        ]
    )
    assert code == 0
    assert (tmp_path / ".git").exists() or (tmp_path / ".git").is_file()
