#!/usr/bin/env python3
# coding=utf-8

"""
tests for send_key name/email index helpers.
"""

from gitks.core.utils import index_filename, index_user_email, index_user_name


def test_index_user_name_and_email_use_separate_keys(tmp_path):
    key_id = "ABCD1234"
    name_path = index_user_name(tmp_path, "Alice Example", key_id)
    email_path = index_user_email(tmp_path, "alice@example.com", key_id)
    assert name_path is not None
    assert email_path is not None
    assert name_path.read_text(encoding="utf-8") == key_id
    assert email_path.read_text(encoding="utf-8") == key_id
    assert name_path.parent.name == "names"
    assert email_path.parent.name == "emails"
    assert name_path.name == index_filename("Alice Example")
    assert email_path.name == index_filename("alice@example.com")


def test_index_skips_empty_name_or_email(tmp_path):
    assert index_user_name(tmp_path, "", "ABCD") is None
    assert index_user_email(tmp_path, "", "ABCD") is None
    assert not (tmp_path / "index").exists()
