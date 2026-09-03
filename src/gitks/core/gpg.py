#!/usr/bin/env python3

"""
GPG helpers for ``gitks`` key validation and detached signatures.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import gnupg
from vt.utils.errors.error_specs import ERR_INVALID_USAGE

from gitks.core.base import KeyValidator
from gitks.core.errors import GitKsException, GitKsExitingException


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


def _show_keys(public_key: bytes | str, gnupghome: str):
    """Inspect key material with GnuPG ``--show-keys`` (no keyring import)."""
    gpg = gnupg.GPG(gnupghome=gnupghome)
    key_file = Path(gnupghome) / "key.asc"
    key_file.write_bytes(as_bytes(public_key))
    # python-gnupg ``scan_keys`` is ``gpg --show-keys`` (dry-run, no import).
    return gpg.scan_keys(str(key_file))


def fingerprint_of(public_key: bytes | str) -> str:
    """
    Read the fingerprint via ``show_keys`` in a throwaway temp GPG home
    (never ``.git`` or the user's default keyring). Keys are not imported.
    """
    with tempfile.TemporaryDirectory(prefix="gitks-gpg-") as td:
        shown = _show_keys(public_key, td)
        fingerprints = [
            normalize_fingerprint(key.get("fingerprint", ""))
            for key in shown
            if key.get("fingerprint")
        ]
        if not fingerprints:
            raise GitKsException("Could not read public key data.")
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
        shown = _show_keys(public_key, str(home))
        if not shown:
            return False
        keyring = home / "pub.gpg"
        gpg_bin = shutil.which("gpg")
        if not gpg_bin:
            return False
        dearmor = subprocess.run(
            [
                gpg_bin,
                "--homedir",
                str(home),
                "--batch",
                "--yes",
                "--dearmor",
                "-o",
                str(keyring),
            ],
            input=as_bytes(public_key),
            capture_output=True,
            check=False,
        )
        if dearmor.returncode != 0 or not keyring.exists():
            return False
        gpg = gnupg.GPG(gnupghome=str(home), keyring=str(keyring))
        sig_path = home / "data.sig"
        sig_path.write_bytes(as_bytes(signature))
        verified = gpg.verify_data(str(sig_path), as_bytes(data))
        return bool(verified)


def detached_sign(data: bytes | str, key_id: str, gnupg_home: Path | str) -> str:
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
        raise GitKsExitingException(
            f"Could not create detached signature with key {key_id}.",
            exit_code=ERR_INVALID_USAGE,
        )
    return str(signed)


class GpgKeyValidator(KeyValidator):
    """Validates that data is an OpenPGP public key (via show_keys, no import)."""

    def validate_key(self, public_key: bytes | str) -> None:
        try:
            fingerprint_of(public_key)
        except GitKsException:
            raise
        except (OSError, ValueError, RuntimeError, UnicodeError) as e:
            raise GitKsException("Public key data is malformed.") from e
