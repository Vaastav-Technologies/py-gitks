#!/usr/bin/env python3
# coding=utf-8

"""
OpenPGP helpers for ``gitks``.

All operations take an explicit GPG home (or a throwaway scratch home). They
never use the process user's default ``~/.gnupg`` unless the caller passes that
path on purpose.
"""

from __future__ import annotations

from contextlib import contextmanager
from email.utils import parseaddr
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from collections.abc import Iterator

import gnupg

_FINGERPRINT_KEY = "fingerprint"
_UIDS_KEY = "uids"


def _as_str(data: bytes | str) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8")
    return data


def _as_signable(data: bytes | str) -> bytes | str:
    """python-gnupg accepts either; keep bytes unchanged."""
    return data


def _gpg(gnupghome: Path | str) -> gnupg.GPG:
    home = Path(gnupghome)
    home.mkdir(parents=True, exist_ok=True)
    return gnupg.GPG(gnupghome=str(home))


@contextmanager
def _scratch_gpg() -> Iterator[gnupg.GPG]:
    """GPG instance whose home is deleted when the block exits."""
    with TemporaryDirectory(prefix="gitks-gpg-") as tmp:
        yield _gpg(tmp)


def _first_public_key_record(public_key: bytes | str) -> dict:
    """
    Read the first public-key packet from ``public_key`` without keeping it
    in a long-lived keyring.
    """
    key_data = _as_str(public_key)
    with _scratch_gpg() as gpg:
        scanned = gpg.scan_keys_mem(key_data)
    if not scanned:
        raise ValueError("No public key found in the supplied key data.")
    return scanned[0]


def _fingerprint_of(record: dict) -> str:
    fingerprint = record.get(_FINGERPRINT_KEY) or record.get("keyid")
    if not fingerprint:
        raise ValueError("Public key has no fingerprint or key id.")
    return str(fingerprint).replace(" ", "").upper()


def _parse_primary_uid(record: dict) -> tuple[str, str]:
    uids = record.get(_UIDS_KEY) or []
    if not uids:
        return "", ""
    name, email = parseaddr(uids[0])
    return name, email


def key_id_from_public_key(public_key: bytes | str) -> str:
    """
    Return a stable id for filenames (OpenPGP fingerprint, no spaces).

    :param public_key: ASCII-armored or binary public key.
    :raise ValueError: If the data does not contain a public key.
    """
    return _fingerprint_of(_first_public_key_record(public_key))


def uid_name_from_public_key(public_key: bytes | str) -> str:
    """
    Return the display name from the primary user id, or ``""``.
    """
    name, _email = _parse_primary_uid(_first_public_key_record(public_key))
    return name


def uid_email_from_public_key(public_key: bytes | str) -> str:
    """
    Return the email from the primary user id, or ``""``.
    """
    _name, email = _parse_primary_uid(_first_public_key_record(public_key))
    return email


def get_key_name_from_key_data(public_key: bytes | str) -> str:
    """
    Key id used in ``send_key`` filenames. Same as ``key_id_from_public_key``.
    """
    return key_id_from_public_key(public_key)


def get_key_user_name(public_key: bytes | str) -> str:
    """Uid display name. Same as ``uid_name_from_public_key``."""
    return uid_name_from_public_key(public_key)


def get_key_user_email(public_key: bytes | str) -> str:
    """Uid email. Same as ``uid_email_from_public_key``."""
    return uid_email_from_public_key(public_key)


def make_detached_signature(public_key: bytes | str, gnupghome: Path | str) -> str:
    """
    Create a detached signature of ``public_key`` using a secret key in ``gnupghome``.

    The signer is the secret key whose fingerprint matches ``public_key``.
    That secret key must already exist in ``gnupghome``.

    :raise ValueError: If signing fails (missing secret key, gpg error, ...).
    """
    key_id = key_id_from_public_key(public_key)
    gpg = _gpg(gnupghome)
    signed = gpg.sign(
        _as_signable(public_key),
        keyid=key_id,
        detach=True,
        clearsign=False,
    )
    signature = str(signed)
    if not getattr(signed, "returncode", 1) == 0 or not signature.strip():
        raise ValueError(
            f"Could not create a detached signature for key {key_id}. "
            "The matching secret key must be present in gnupghome."
        )
    return signature


def verify_detached_signature(
    public_key: bytes | str, signature: str, gnupghome: Path | str
) -> bool:
    """
    Return whether ``signature`` is a valid detached signature of ``public_key``.

    Imports ``public_key`` into ``gnupghome`` (public keyring only) so gpg can
    check the signature. Does not require the requester's secret key.
    """
    gpg = _gpg(gnupghome)
    imported = gpg.import_keys(_as_str(public_key))
    if imported.count == 0:
        return False
    with NamedTemporaryFile(
        prefix="gitks-sig-", suffix=".asc", delete=False, mode="w", encoding="utf-8"
    ) as sig_file:
        sig_file.write(signature)
        sig_path = sig_file.name
    try:
        data = public_key if isinstance(public_key, bytes) else public_key.encode("utf-8")
        verified = gpg.verify_data(sig_path, data)
    finally:
        Path(sig_path).unlink(missing_ok=True)
    return bool(getattr(verified, "valid", False))


def first_secret_key_id(gnupghome: Path | str) -> str | None:
    """
    Return the fingerprint of the first secret key in ``gnupghome``, or ``None``.
    """
    gpg = _gpg(gnupghome)
    secrets = gpg.list_keys(secret=True)
    if not secrets:
        return None
    fingerprint = secrets[0].get(_FINGERPRINT_KEY) or secrets[0].get("keyid")
    if not fingerprint:
        return None
    return str(fingerprint).replace(" ", "").upper()


def owner_sign_data(
    data: bytes | str, gnupghome: Path | str, owner_key_id: str
) -> str:
    """
    Create a detached signature of ``data`` with the owner's key ``owner_key_id``.

    ``owner_key_id`` is a fingerprint or key id gpg accepts. The matching
    secret key must exist in ``gnupghome``.

    :raise ValueError: If signing fails.
    """
    gpg = _gpg(gnupghome)
    signed = gpg.sign(
        _as_signable(data),
        keyid=owner_key_id,
        detach=True,
        clearsign=False,
    )
    signature = str(signed)
    if not getattr(signed, "returncode", 1) == 0 or not signature.strip():
        raise ValueError(
            f"Could not sign data with owner key {owner_key_id}. "
            "That secret key must be present in gnupghome."
        )
    return signature
