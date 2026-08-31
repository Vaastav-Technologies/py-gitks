#!/usr/bin/env python3
# coding=utf-8

"""
UniSign: signing interface for ``gitks``.

This is the contract only. A concrete implementation will be supplied to users
separately; gitks must not assume a particular GPG/homedir layout here.
"""

from abc import abstractmethod
from typing import Protocol


class UniSign(Protocol):
    """
    Requester identity is established by a detached signature of their own
    public key, plus a bind signature of the request payload that verifies
    with that same public key. Git ``commit -S`` will be added on this
    interface when the UniSign implementation is supplied.
    """

    @abstractmethod
    def detach_sign(self, data: bytes | str, key_id: str) -> str:
        """Return an armored detached signature of ``data`` by ``key_id``."""
        ...

    @abstractmethod
    def verify_detached(
        self,
        data: bytes | str,
        signature: bytes | str,
        public_key: bytes | str,
    ) -> bool:
        """Return True if ``signature`` is a valid detached signature of ``data`` by ``public_key``."""
        ...

    # Git commit -S signing will live on this interface when the
    # implementation is provided. Until then gitks binds requests with a
    # detached signature of the request payload that verifies with the
    # requester's public key.
