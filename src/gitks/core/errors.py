#!/usr/bin/env python3
# coding=utf-8

"""
Exceptions related tp ``gitks``.
"""

from vt.utils.errors.error_specs.exceptions import VTExitingException


class KeyServerException(VTExitingException):
    """
    Exception related to keyserver.
    """

    pass


class GitKsException(KeyServerException):
    """
    Exception related to ``gitks``
    """

    pass

class KeyNotPendingError(GitKsException):
    """approve/deny when the key is not in requests."""

class KeySignatureError(GitKsException):
    """detached signature does not match the public key."""
