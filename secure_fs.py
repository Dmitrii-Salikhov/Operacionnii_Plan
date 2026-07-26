"""Ограничение прав на локальные секретные файлы (credentials, token)."""

from __future__ import annotations

import getpass
import os
import stat
import subprocess


def harden_secret_file(path: str) -> None:
    """Делает файл доступным только текущему пользователю (best-effort)."""
    if not path or not os.path.exists(path):
        return
    try:
        if os.name == "nt":
            user = getpass.getuser()
            # Снять наследование и выдать Full Control только себе.
            subprocess.run(
                ["icacls", path, "/inheritance:r", "/grant:r", f"{user}:F"],
                check=False,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0,
            )
        else:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def write_secret_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
    harden_secret_file(path)


def write_secret_text(path: str, text: str, encoding: str = "utf-8") -> None:
    write_secret_bytes(path, text.encode(encoding))
