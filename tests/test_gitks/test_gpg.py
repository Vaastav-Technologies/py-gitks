#!/usr/bin/env python3
# coding=utf-8

"""
tests for OpenPGP helpers. GPG homes are always under pytest tmp_path.
"""

from pathlib import Path

import pytest

from gitks.core.gpg import (
    get_key_name_from_key_data,
    get_key_user_email,
    get_key_user_name,
    key_id_from_public_key,
    make_detached_signature,
    owner_sign_data,
    uid_email_from_public_key,
    uid_name_from_public_key,
    verify_detached_signature,
)

gnupg = pytest.importorskip("gnupg")


def _gpg_home(tmp_path: Path, name: str) -> Path:
    home = tmp_path / name
    home.mkdir()
    return home


def _generate_keypair(home: Path, real_name: str, email: str):
    gpg = gnupg.GPG(gnupghome=str(home))
    params = gpg.gen_key_input(
        key_type="EDDSA",
        key_curve="Ed25519",
        name_real=real_name,
        name_email=email,
        no_protection=True,
        expire_date="0",
    )
    generated = gpg.gen_key(params)
    if not generated.fingerprint:
        params = gpg.gen_key_input(
            key_type="RSA",
            key_length=2048,
            name_real=real_name,
            name_email=email,
            no_protection=True,
            expire_date="0",
        )
        generated = gpg.gen_key(params)
    assert generated.fingerprint, f"gpg key generation failed: {generated.stderr}"
    public_key = gpg.export_keys(generated.fingerprint)
    assert public_key
    return generated.fingerprint.replace(" ", "").upper(), public_key


@pytest.fixture(scope="module")
def alice_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("gpg-alice")
    fingerprint, public_key = _generate_keypair(
        home, "Alice Example", "alice@example.com"
    )
    return home, fingerprint, public_key


@pytest.fixture(scope="module")
def owner_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("gpg-owner")
    fingerprint, public_key = _generate_keypair(
        home, "Repo Owner", "owner@example.com"
    )
    return home, fingerprint, public_key


class TestPublicKeyMetadata:
    def test_key_id_is_fingerprint(self, alice_home):
        _home, fingerprint, public_key = alice_home
        assert key_id_from_public_key(public_key) == fingerprint

    def test_uid_name_and_email(self, alice_home):
        _home, _fp, public_key = alice_home
        assert uid_name_from_public_key(public_key) == "Alice Example"
        assert uid_email_from_public_key(public_key) == "alice@example.com"

    def test_rejects_garbage(self):
        with pytest.raises(ValueError, match="No public key"):
            key_id_from_public_key("not-a-key")

    def test_send_key_helper_aliases(self, alice_home):
        _home, fingerprint, public_key = alice_home
        assert get_key_name_from_key_data(public_key) == fingerprint
        assert get_key_user_name(public_key) == "Alice Example"
        assert get_key_user_email(public_key) == "alice@example.com"


class TestDetachedSignature:
    def test_round_trip_valid(self, alice_home, tmp_path):
        alice_dir, _fp, public_key = alice_home
        signature = make_detached_signature(public_key, alice_dir)
        verify_home = _gpg_home(tmp_path, "verify-alice")
        assert verify_detached_signature(public_key, signature, verify_home) is True

    def test_wrong_data_is_invalid(self, alice_home, tmp_path):
        alice_dir, _fp, public_key = alice_home
        signature = make_detached_signature(public_key, alice_dir)
        verify_home = _gpg_home(tmp_path, "verify-bad")
        # Signature was over the original key; extra bytes must not verify.
        assert (
            verify_detached_signature(public_key + "\n", signature, verify_home)
            is False
        )

    def test_sign_without_secret_key_fails(self, alice_home, tmp_path):
        _alice_dir, _fp, public_key = alice_home
        empty_home = _gpg_home(tmp_path, "empty")
        with pytest.raises(ValueError, match="detached signature"):
            make_detached_signature(public_key, empty_home)


class TestOwnerSign:
    def test_owner_can_sign_arbitrary_data(self, owner_home, tmp_path):
        owner_dir, owner_id, owner_pub = owner_home
        payload = "attestation-for-key-ABCD"
        signature = owner_sign_data(payload, owner_dir, owner_id)
        verify_home = _gpg_home(tmp_path, "verify-owner")
        import gnupg as _gnupg

        gpg = _gnupg.GPG(gnupghome=str(verify_home))
        gpg.import_keys(owner_pub)
        from tempfile import NamedTemporaryFile
        from pathlib import Path as P

        with NamedTemporaryFile(
            prefix="own-sig-", suffix=".asc", delete=False, mode="w", encoding="utf-8"
        ) as sig_file:
            sig_file.write(signature)
            sig_path = sig_file.name
        try:
            verified = gpg.verify_data(sig_path, payload.encode("utf-8"))
        finally:
            P(sig_path).unlink(missing_ok=True)
        assert verified.valid
