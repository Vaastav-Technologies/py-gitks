#!/usr/bin/env python3
# coding=utf-8

"""
GPG key validation for ``gitks``.
"""

import tempfile

import gnupg


class GPGKeyValidator:
    """
    GPG-backed implementation of the key validator.

    Validation is delegated to GPG through ``python-gnupg``.
    A temporary GPG home is used so validation does not modify the
    user's existing GPG keyring.
    """

    def validate_key(self, public_key: bytes | str) -> None:
        """
        Validate the supplied GPG public key.

        GPG is responsible for parsing and validating the key data.
        Secret/private keys are explicitly rejected.

        :param public_key: GPG key data to validate.
        :raise SyntaxError: If the key data is malformed or cannot
            be processed as valid OpenPGP data.
        :raise ValueError: If the supplied data contains a secret key
            or is otherwise not a valid public key.
        """

        with tempfile.TemporaryDirectory() as gpg_home:
            gpg = gnupg.GPG(gnupghome=gpg_home)

            result = gpg.import_keys(public_key)

            if result.sec_read > 0 or result.sec_imported > 0:
                raise ValueError(
                    "Private/secret keys are not allowed."
                )

            if not result.fingerprints:
                raise SyntaxError(
                    "The supplied key could not be processed by GPG."
                )

            if result.imported <= 0:
                raise ValueError(
                    "The supplied key is not a valid public key."
                )
