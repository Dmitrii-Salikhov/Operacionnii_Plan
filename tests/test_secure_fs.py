"""Тесты прав на секретные файлы."""

import os
import stat

from secure_fs import harden_secret_file, write_secret_bytes, write_secret_text


def test_harden_secret_file_unix(tmp_path):
    if os.name == "nt":
        return
    path = tmp_path / "secret.json"
    write_secret_text(str(path), '{"x":1}')
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    write_secret_bytes(str(path), b"abc")
    harden_secret_file(str(path))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
