#!/usr/bin/env python3

"""
Exceptions related to ``gitks``.
"""

from vt.utils.errors.error_specs.exceptions import VTException, VTExitingException


class GitKsException(VTException):
    """
    Exception related to ``gitks``.
    """


class GitKsExitingException(VTExitingException):
    """
    ``gitks`` exception that carries an application exit code.
    """


class KeyServerException(GitKsExitingException):
    """
    Exception related to keyserver.
    """
