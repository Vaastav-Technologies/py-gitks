#!/usr/bin/env python3
# coding=utf-8

"""
Key import contract for ``gitks``.

Do not import keys into ``.git`` GPG homedirs. Tests must use an isolated GPG home.
"""

from abc import abstractmethod
from typing import Protocol

from gitks.core.errors import GitKsException
from vt.utils.errors.error_specs import ERR_INVALID_USAGE


class KeyImporter(Protocol):
    """Import public keys into a GPG keyring."""

    @abstractmethod
    def import_keys_dry_run(self, public_key: bytes | str) -> None:
        """Validate what an import would do without changing any keyring."""
        # TODO: Deferred until Trinay's dry-run logic is available.
        ...

    @abstractmethod
    def import_keys(self, public_key: bytes | str) -> None:
        """Import ``public_key`` into the configured GPG home."""
        # TODO: Must not run against the user's live keyring until dry-run is complete.
        ...


class DeferredKeyImporter:
    """Placeholder: no live-keyring import until dry-run exists."""

    def import_keys_dry_run(self, public_key: bytes | str) -> None:
        # TODO: Deferred until Trinay's dry-run logic is available.
        raise GitKsException(
            "Key import dry-run is not available yet.",
            exit_code=ERR_INVALID_USAGE,
        )

    def import_keys(self, public_key: bytes | str) -> None:
        # TODO: Deferred until Trinay's dry-run logic is available.
        raise GitKsException(
            "Direct GPG import is deferred until key import dry-run is complete. "
            "Do not import into .git GPG directories or the user's default keyring.",
            exit_code=ERR_INVALID_USAGE,
        )
