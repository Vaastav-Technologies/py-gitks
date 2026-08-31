#!/usr/bin/env python3
# coding=utf-8

"""
GPG helpers for ``gitks`` key validation and detached signatures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import gnupg

from gitks.core.base import KeyValidator


def as_str(data: bytes | str) -> str:
    if isinstance(data, bytes):
        return data.decode()
    return data


def as_bytes(data: bytes | str) -> bytes:
    if isinstance(data, str):
        return data.encode()
    return data


def normalize_fingerprint(fingerprint: str) -> str:
    return fingerprint.replace(" ", "").upper()


def fingerprint_of(public_key: bytes | str) -> str:
    """
    Read the fingerprint via a throwaway temp GPG home (never ``.git`` or the
    user's default keyring).
    """
    with tempfile.TemporaryDirectory(prefix="gitks-gpg-") as td:
        gpg = gnupg.GPG(gnupghome=td)
        imported = gpg.import_keys(as_str(public_key))
        fingerprints = [
            normalize_fingerprint(fp) for fp in (imported.fingerprints or []) if fp
        ]
        if not fingerprints:
            raise ValueError("Could not import public key data.")
        return fingerprints[0]


def verify_detached_signature(
    public_key: bytes | str, data: bytes | str, signature: bytes | str
) -> bool:
    """
    Return True if ``signature`` is a valid detached signature of ``data``
    made by ``public_key``.
    """
    with tempfile.TemporaryDirectory(prefix="gitks-gpg-verify-") as td:
        home = Path(td)
        gpg = gnupg.GPG(gnupghome=str(home))
        imported = gpg.import_keys(as_str(public_key))
        if not imported.fingerprints:
            return False
        sig_path = home / "data.sig"
        sig_path.write_bytes(as_bytes(signature))
        verified = gpg.verify_data(str(sig_path), as_bytes(data))
        return bool(verified)


def detached_sign(
    data: bytes | str, key_id: str, gnupg_home: Path | str
) -> str:
    """
    Create an armored detached signature of ``data`` using ``key_id`` in ``gnupg_home``.
    """
    gpg = gnupg.GPG(gnupghome=str(gnupg_home))
    signed = gpg.sign(
        as_str(data),
        keyid=normalize_fingerprint(key_id),
        detach=True,
        extra_args=["--yes"],
    )
    if not getattr(signed, "data", None):
        raise ValueError(
            f"Could not create detached signature with key {key_id}."
        )
    return str(signed)


class GpgKeyValidator(KeyValidator):
    """Validates that data is an importable OpenPGP public key."""

    def validate_key(self, public_key: bytes | str) -> None:
        try:
            fingerprint_of(public_key)
        except ValueError as e:
            raise ValueError(str(e)) from e
        except Exception as e:
            raise SyntaxError("Public key data is malformed.") from e
