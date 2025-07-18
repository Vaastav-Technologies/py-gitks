#!/usr/bin/env python3
# coding=utf-8

"""
interfaces related to keyserver workings for ``gitks``.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Protocol, overload

from vt.utils.commons.commons.op import RootDirOp

from gitks.core.constants import GIT_KS_KEYS_BASE_BRANCH, GIT_KS_DIR, SELF_REPO
from gitks.core.model import KeyUploadResult, KeyData, KeyDeleteResult, KeyServerConnectResult, GitKSCloneResult, \
    GitSelf


class KeyValidator(Protocol):
    """
    A validator for keys.
    """

    def validate_key(self, public_key: bytes | str) -> None:
        """
        Validate that the supplied key data is valid.

        :param public_key: the key data to be validated.
        :raise ValueError: If key fails using the rules defined by the key validator.
        :raise SyntaxError: If key data is malformed.
        """
        ...


class HasKeyValidator(Protocol):
    """
    Interface to signify that a certain interface encapsulates a key-validator.
    """

    @property
    @abstractmethod
    def key_validator(self) -> KeyValidator:
        """
        :return: The validator that performs key validation.
        """
        ...


class KeySender(HasKeyValidator, Protocol):
    """
    Interface for a key sender to a key-server.
    """

    @abstractmethod
    def send_key(self, public_key: bytes | str) -> KeyUploadResult:
        """
        Send key to a keyserver.

        :param public_key: the public key data to be sent to the keyserver.
        :return: ``KeyUploadResult`` with extensive context on key's upload status.
        :raise ValueError: If key fails using the rules defined by the key validator.
        :raise SyntaxError: If key data is malformed.
        """
        ...


class KeyReceiver(HasKeyValidator, Protocol):
    """
    Interface for a key receiver to receive a key from the key-server.
    """

    @abstractmethod
    def receive_key(self, key_id: str) -> bytes | str:
        """
        Send key to a keyserver.

        :param key_id: exact key-id to receive from the keyserver.
        :return: ``True`` if key was uploaded. ``False`` if key was not uploaded.
        :raise ValueError: If key fails using the rules defined by the key validator.
        :raise SyntaxError: If key data is malformed.
        """
        ...


class KeySearcher(Protocol):
    """
    Interface to search keys from a keyserver.
    """

    @abstractmethod
    def search_keys(self, key_search_str: str) -> list[KeyData]:
        """
        :param key_search_str: a search expression that can be used to search keys from the keyserver.
        :return: list of keys fetchable form the supplied ``key_search_str``.
        """
        ...


class KeyDeleter(Protocol):
    """
    Interface to delete keys from a keyserver.
    """

    @abstractmethod
    def delete_key(self, key_id: str) -> KeyDeleteResult:
        """
        Delete key from a keyserver using the supplied ``key_id``.

        :param key_id: exact key_id to delete from the keyserver.
        :return:
        """
        ...


class KeyServer(Protocol):
    """
    Interface of a keyserver.
    """

    ...


class KeyServerClient(KeySender, KeyReceiver, KeySearcher, KeyDeleter, Protocol):
    """
    Interface of a keyserver. Can:

    - search keys using a search query.
    - receive key with exact key id.
    - send key with exact key data.
    - delete key with exact key id.
    """

    @abstractmethod
    def register(self, url: str) -> KeyServerConnectResult:
        """
        Register self to the keyserver present at url ``url``.

        :param url: the keyserver url to connect to.
        :return: connection result.
        """

        ...


class GitKeyServer(KeyServer, RootDirOp, Protocol):
    """
    Interface for git keyserver.
    """

    @abstractmethod
    def init(
        self, keys_base_branch: str = GIT_KS_KEYS_BASE_BRANCH, git_ks_dir: Path = GIT_KS_DIR
    ) -> None:
        """
        Initialise the gitks repo. Initialises:

        - branch where keys are put to and retrieved from.
        - Root directory where these keys will be kept offline/on client machine.

        :param keys_base_branch: base branch name where keys will be stored.
        :param git_ks_dir: gitks root directory which will have keys offline. This is the path from repo root.
        """
        ...


class GitKeyServerClient(KeyServerClient, RootDirOp, Protocol):
    """
    Interface for git keyserver client
    """

    @overload
    @abstractmethod
    def clone(self, *, url: GitSelf = SELF_REPO, base_dir: GitSelf = SELF_REPO) -> GitKSCloneResult:
        ...

    @overload
    @abstractmethod
    def clone(self, *, url: str, base_dir: Path | None = None) -> GitKSCloneResult:
        ...

    @abstractmethod
    def clone(self, *, url: str | GitSelf = SELF_REPO, base_dir: Path | None | GitSelf = SELF_REPO) -> GitKSCloneResult:
        """
        Clone the git repo acting as a keyserver into a specified ``base_dir``.

        :param url: source of the git repo.
        :param base_dir: directory where this repo will be cloned into. Defaults to ``__SELF_REPO__``, denoting that
            this repo itself is the git keyserver. ``None`` means to use the default location (determined by
            the implementation).
        :return: the clone (and hence, connect) result of git keyserver client.
        """

        ...
