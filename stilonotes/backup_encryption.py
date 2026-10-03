# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Standalone GPG symmetric encryption and decryption for Stilo Notes backups.
Uses standard AES-256 password-based encryption with no dependency on system
GPG keyring or configuration.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def is_gpg_available() -> bool:
    """Check if the gpg executable is available in PATH."""
    return bool(shutil.which("gpg") or shutil.which("gpg2"))


def get_gpg_command() -> str:
    """Return the gpg binary name or path."""
    bin_path = shutil.which("gpg") or shutil.which("gpg2")
    if not bin_path:
        raise RuntimeError("GPG executable (gpg or gpg2) was not found in system PATH.")
    return bin_path


def is_encrypted_file(file_path: str) -> bool:
    """
    Check if a file is an encrypted backup (not a plain SQLite database).
    Plain SQLite databases begin with the 'SQLite format 3\\x00' magic header.
    """
    path = Path(file_path)
    if not path.is_file():
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return not header.startswith(b"SQLite format 3\x00")
    except Exception:
        return False


def encrypt_file(source_path: str, target_path: str, password: str):
    """
    Encrypt a source file to target_path using GPG symmetric AES-256 encryption.
    Does not use or touch system GPG keys or configuration.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    gpg_bin = get_gpg_command()
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        gpg_bin,
        "--batch",
        "--yes",
        "--pinentry-mode", "loopback",
        "--passphrase-fd", "0",
        "--symmetric",
        "--cipher-algo", "AES256",
        "--no-options",
        "--no-default-keyring",
        "-o", str(target),
        str(src),
    ]

    proc = subprocess.run(
        cmd,
        input=password.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Encryption failed: {err}")


def decrypt_file(source_path: str, target_path: str, password: str):
    """
    Decrypt a GPG-encrypted backup file to target_path using password.
    Raises ValueError on incorrect password, or RuntimeError on other errors.
    """
    gpg_bin = get_gpg_command()
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        gpg_bin,
        "--batch",
        "--yes",
        "--pinentry-mode", "loopback",
        "--passphrase-fd", "0",
        "--decrypt",
        "--no-options",
        "--no-default-keyring",
        "-o", str(target),
        str(src),
    ]

    proc = subprocess.run(
        cmd,
        input=password.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        err_lower = err.lower()
        if "bad session key" in err_lower or "decryption failed" in err_lower:
            raise ValueError("Incorrect password or corrupted backup file.")
        raise RuntimeError(f"Decryption failed: {err}")
