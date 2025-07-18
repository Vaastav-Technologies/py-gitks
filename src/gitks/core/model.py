#!/usr/bin/env python3
# coding=utf-8

"""
models related to keyserver workings for ``gitks``.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from vt.utils.commons.commons.core_py.base import Sentinel


# region key upload models
class KeyUploadStatus(Enum):
    SUCCESS = "success"
    ALREADY_EXISTS = "already_exists"
    INVALID_KEY = "invalid"
    ERROR = "error"


@dataclass
class KeyUploadResult:
    status: KeyUploadStatus
    message: str | None = None
    server_id: str | None = None  # e.g., Git commit hash or keyserver fingerprint


# endregion


# region key delete models
class KeyDeleteStatus(Enum):
    SUCCESS = "success"
    DOES_NOT_EXIST = "does_not_exist"
    ERROR = "error"


@dataclass
class KeyDeleteResult:
    status: KeyDeleteStatus
    message: str | None = None
    server_id: str | None = None


# endregion


@dataclass
class KeyData:
    key_id: str
    raw_bytes: bytes
    format: str  # e.g., "PGP", "PEM", "SSH"
    created_at: datetime | None = None


@dataclass
class KeyServerConnectResult:
    connected: bool
    message: str
    details: dict[str, str]
    code: int


@dataclass
class GitKSCloneResult(KeyServerConnectResult):
    repo_path: Path | None


class GitSelf(Sentinel):
    """
    Sentinel denoting the same repo is keyserver as well as keyserver client.
    """

    def __init__(self, str_name: str):
        self.str_name = str_name

    def __str__(self) -> str:
        return self.str_name
