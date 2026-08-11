import hashlib
import json
import urllib.error

import updater
from updater import compute_sha256, find_release_asset, parse_sha256_text, parse_version


def test_parse_version_handles_valid_and_invalid_tags():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("2.0") == (2, 0)
    assert parse_version("broken") == (0, 0, 0)
    assert parse_version(None) == (0, 0, 0)


def test_parse_sha256_text_supports_supported_formats():
    digest = "a" * 64
    assert parse_sha256_text(digest) == digest
    assert parse_sha256_text(f"{digest}  PlanOperaciy-Windows.zip") == digest
    assert parse_sha256_text(f"{digest} *PlanOperaciy-Windows.zip") == digest
    assert parse_sha256_text(f"{digest} another.zip") is None
    assert parse_sha256_text(f"# comment\nnot-a-hash\n{digest} *nested/PlanOperaciy-Windows.zip") == digest
    assert parse_sha256_text(f"{digest[:-1]}z") is None


def test_compute_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "archive.zip"
    path.write_bytes(b"known archive contents")
    assert compute_sha256(path) == hashlib.sha256(b"known archive contents").hexdigest()


def test_find_release_asset_works_without_network():
    release = {"assets": [{"name": "one.zip"}, {"name": "two.sha256"}]}
    assert find_release_asset(release, "two.sha256") == {"name": "two.sha256"}
    assert find_release_asset(release, "absent") is None


def test_current_version_and_asset_url_use_local_data(tmp_path, monkeypatch):
    (tmp_path / "version.txt").write_text("1.4.0\n", encoding="utf-8")
    monkeypatch.setattr(updater, "get_base_dir", lambda: str(tmp_path))
    assert updater.read_current_version() == "1.4.0"
    good = (
        "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/download/v1/a.zip"
    )
    assert updater._asset_download_url({"browser_download_url": good}) == good
    assert updater._asset_download_url({"browser_download_url": "https://evil.test/a.zip"}) is None
    assert updater._asset_download_url({}) is None


def test_trusted_urls():
    assert updater.is_trusted_download_url(
        "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/download/v1/x.zip"
    )
    assert not updater.is_trusted_download_url("http://github.com/Dmitrii-Salikhov/Operacionnii_Plan/x")
    assert not updater.is_trusted_download_url(
        "https://github.com/other/Operacionnii_Plan/releases/download/v1/x.zip"
    )
    assert updater.is_trusted_release_page_url(
        "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/tag/v1.1.0"
    )
    assert not updater.is_trusted_release_page_url("https://evil.example/releases")


def test_fetch_latest_release_and_download_retries_are_network_free(tmp_path, monkeypatch):
    release = {"tag_name": "v2.0.0", "assets": []}
    monkeypatch.setattr(updater, "_http_get", lambda *args, **kwargs: json.dumps(release).encode())
    assert updater.fetch_latest_release() == release
    assert updater.get_latest_version() == "v2.0.0"

    attempts = []

    def download_then_succeed(url, dest_path, timeout=120, chunk_size=1024 * 1024):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError("temporary")
        with open(dest_path, "wb") as f:
            f.write(b"archive")
        return len(b"archive")

    monkeypatch.setattr(updater, "_http_download_to_file", download_then_succeed)
    monkeypatch.setattr(updater.time, "sleep", lambda _: None)
    output = tmp_path / "download.zip"
    assert updater.download_with_retries("https://example.test/archive", output, max_retries=2)
    assert output.read_bytes() == b"archive"


def test_fetch_and_download_failures_return_safe_values(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_http_get", lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    assert updater.fetch_latest_release() is None
    monkeypatch.setattr(
        updater,
        "_http_download_to_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    assert not updater.download_with_retries("https://example.test/archive", tmp_path / "no.zip", max_retries=1)
    removable = tmp_path / "remove-me"
    removable.write_text("x", encoding="utf-8")
    updater._safe_remove(removable)
    assert not removable.exists()


def test_get_latest_version_handles_failed_release(monkeypatch):
    monkeypatch.setattr(updater, "fetch_latest_release", lambda: None)
    assert updater.get_latest_version() is None


def test_check_for_updates_silently_handles_current_and_failed_releases(monkeypatch):
    logs = []
    monkeypatch.setattr(updater, "_log", logs.append)
    monkeypatch.setattr(updater, "fetch_latest_release", lambda: {"tag_name": "v1.2.3"})
    updater.check_for_updates("1.2.3", silent_if_updated=True)
    assert "Обновлений нет" in logs[-1]

    monkeypatch.setattr(updater, "fetch_latest_release", lambda: None)
    updater.check_for_updates("1.2.3", silent_if_updated=True)


def test_perform_update_reports_missing_release_assets(monkeypatch):
    messages = []
    monkeypatch.setattr(updater.messagebox, "showerror", lambda *args: messages.append(args))
    updater.perform_update("/unused", release={"assets": []})
    good = "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/download/v1/PlanOperaciy-Windows.zip"
    updater.perform_update(
        "/unused",
        release={
            "assets": [
                {"name": updater.ZIP_FILENAME, "browser_download_url": good},
            ]
        },
    )
    assert len(messages) == 2
    assert "нет файла" in messages[0][1] or "контрольной суммы" in messages[0][1]
    assert "контрольной суммы" in messages[1][1]


def test_perform_update_rejects_invalid_or_mismatched_checksum(tmp_path, monkeypatch):
    messages = []

    class Window:
        def title(self, *_):
            pass

        def geometry(self, *_):
            pass

        def resizable(self, *_):
            pass

        def update(self):
            pass

        def destroy(self):
            pass

    class Label:
        def __init__(self, *_, **__):
            pass

        def pack(self, **_):
            pass

    base = "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/download/v1/"
    release = {
        "html_url": "https://github.com/Dmitrii-Salikhov/Operacionnii_Plan/releases/tag/v1",
        "assets": [
            {"name": updater.ZIP_FILENAME, "browser_download_url": base + "PlanOperaciy-Windows.zip"},
            {"name": updater.SHA256_FILENAME, "browser_download_url": base + "PlanOperaciy-Windows.zip.sha256"},
        ],
    }
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.tk, "Toplevel", Window)
    monkeypatch.setattr(updater.tk, "Label", Label)
    monkeypatch.setattr(updater.messagebox, "showerror", lambda *args: messages.append(args))

    def write_invalid_checksum(_, path, **kwargs):
        path = __import__("pathlib").Path(path)
        if path.suffix == ".sha256":
            path.write_text("not a checksum", encoding="utf-8")
        else:
            path.write_bytes(b"zip")
        return True

    monkeypatch.setattr(updater, "download_with_retries", write_invalid_checksum)
    updater.perform_update("/unused", release=release)
    assert "неизвестный формат" in messages[-1][1]

    def write_mismatched_checksum(_, path, **kwargs):
        path = __import__("pathlib").Path(path)
        if path.suffix == ".sha256":
            path.write_text("0" * 64, encoding="utf-8")
        else:
            path.write_bytes(b"zip")
        return True

    monkeypatch.setattr(updater, "download_with_retries", write_mismatched_checksum)
    updater.perform_update("/unused", release=release)
    assert "не совпала" in messages[-1][1]


def test_write_update_cmd_script_supports_cyrillic_paths(tmp_path):
    script = tmp_path / "update_plan.cmd"
    app_dir = str(tmp_path / "Документы" / "ПланОпераций")
    zip_path = str(tmp_path / "архив.zip")
    sha_path = str(tmp_path / "сумма.sha256")
    updater.write_update_cmd_script(str(script), app_dir, zip_path, extra_cleanup=[sha_path])
    raw = script.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    text = raw.decode("utf-8-sig")
    assert "ПланОпераций" in text
    assert "PlanOperaciy.exe" in text
    assert "tar -xf" in text
    assert "ExecutionPolicy" not in text
    assert "Bypass" not in text


def test_write_update_powershell_script_supports_cyrillic_paths(tmp_path):
    script = tmp_path / "update_plan.ps1"
    app_dir = str(tmp_path / "Документы" / "ПланОпераций")
    zip_path = str(tmp_path / "архив.zip")
    sha_path = str(tmp_path / "сумма.sha256")
    updater.write_update_powershell_script(str(script), app_dir, zip_path, sha_path)
    raw = script.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "cmd.exe" in text
    assert (tmp_path / "update_plan.cmd").exists()
