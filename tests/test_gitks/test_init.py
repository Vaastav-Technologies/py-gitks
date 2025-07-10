#!/usr/bin/env python3
# coding=utf-8

"""
tests relating to ``gitks init`` operation.
"""
from gitks.core.impl import GitKeyServerImpl


def test_simple_init(repo_local):
    ks = GitKeyServerImpl(None, repo_local)
    ks.init()
