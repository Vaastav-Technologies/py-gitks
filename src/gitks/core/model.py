#!/usr/bin/env python3
# coding=utf-8

"""
models related to keyserver workings for ``gitks``.
"""

from datetime import datetime
from enum import Enum
from dataclasses import dataclass


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
