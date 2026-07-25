"""
Модуль автообновления: проверка, скачивание и установка новой версии.

Защита:
- TLS с проверкой сертификатов (certifi / системное хранилище)
- проверка SHA-256 архива по файлу *.sha256 рядом с релизом на GitHub
"""
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import messagebox

GITHUB_REPO = "Dmitrii-Salikhov/Operacionnii_Plan"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ZIP_FILENAME = "PlanOperaciy-Windows.zip"
SHA256_FILENAME = f"{ZIP_FILENAME}.sha256"
USER_AGENT = "PlanOperaciy-Updater"


def get_base_dir():
    """Возвращает папку, где находится исполняемый файл (exe или .py)."""
    env = os.environ.get("PLAN_BASE_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _log(message):
    from app_logging import append_update_log

    append_update_log(message, get_base_dir())


def _ssl_context():
    """TLS-контекст с проверкой сертификатов (без CERT_NONE)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read()


def fetch_latest_release():
    """Скачивает JSON последнего релиза GitHub или None при ошибке."""
    try:
        data = json.loads(_http_get(API_URL, timeout=10).decode("utf-8"))
        tag = data.get("tag_name")
        _log(f"Получен тег: {tag}")
        return data
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        _log(f"Ошибка проверки обновлений: {e}")
        return None


def get_latest_version():
    """Возвращает строку с последней версией (например, 'v1.0.1') или None."""
    release = fetch_latest_release()
    if not release:
        return None
    return release.get("tag_name")


def parse_version(tag):
    """Преобразует тег 'v1.2.3' или '1.2.3' в кортеж чисел (1, 2, 3)."""
    if tag:
        v = tag.lstrip("v")
        parts = v.split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0)


def read_current_version():
    """Читает локальный version.txt — единственный источник номера версии приложения."""
    try:
        version_path = os.path.join(get_base_dir(), "version.txt")
        with open(version_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def find_release_asset(release, filename):
    for asset in release.get("assets") or []:
        if asset.get("name") == filename:
            return asset
    return None


def parse_sha256_text(text, expected_filename=ZIP_FILENAME):
    """
    Извлекает hex SHA-256 из содержимого .sha256 / SHA256SUMS.
    Поддерживает форматы:
      <hash>
      <hash>  <filename>
      <hash> *<filename>
    """
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(
            r"^([A-Fa-f0-9]{64})(?:\s+\*?(\S+))?$",
            line,
        )
        if not match:
            continue
        digest, name = match.group(1), match.group(2)
        if name is None or os.path.basename(name) == expected_filename:
            return digest.lower()
    return None


def compute_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_with_retries(url, dest_path, max_retries=7, timeout=60):
    """
    Скачивает файл с экспоненциальной задержкой между попытками.
    Возвращает True в случае успеха, иначе False.
    """
    for attempt in range(1, max_retries + 1):
        try:
            data = _http_get(url, timeout=timeout)
            with open(dest_path, "wb") as out_file:
                out_file.write(data)
            return True
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as e:
            _log(f"Ошибка скачивания (попытка {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                return False
            wait_seconds = 3 * (2 ** (attempt - 1))
            time.sleep(wait_seconds)
    return False


def _asset_download_url(asset):
    return asset.get("browser_download_url")


def write_update_powershell_script(ps_script, app_dir, zip_path, sha_path):
    """
    Пишет .ps1 для замены файлов после выхода из приложения.
    UTF-8 с BOM — чтобы кириллица в путях не ломала запись/чтение на Windows.
    Сохраняет пользовательские файлы (calendars/credentials/token и т.п.),
    т.к. Expand-Archive -Force не удаляет отсутствующие в zip файлы.
    """
    ps_app_dir = app_dir.replace("\\", "\\\\")
    ps_zip = zip_path.replace("\\", "\\\\")
    ps_sha = sha_path.replace("\\", "\\\\")
    ps_exe = os.path.join(app_dir, "PlanOperaciy.exe").replace("\\", "\\\\")
    commands = f"""
$ErrorActionPreference = "Stop"
$timeout = 80
$names = @("PlanOperaciy", "PlanOperaciyBackend", "electron")
foreach ($n in $names) {{
    Get-Process -Name $n -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}}
for ($i=0; $i -lt $timeout; $i++) {{
    $left = Get-Process -Name "PlanOperaciy" -ErrorAction SilentlyContinue
    if (-not $left) {{ break }}
    Start-Sleep -Milliseconds 100
}}
Expand-Archive -Path "{ps_zip}" -DestinationPath "{ps_app_dir}" -Force
if (Test-Path "{ps_app_dir}\\_internal\\version.txt") {{
    Move-Item -Path "{ps_app_dir}\\_internal\\version.txt" -Destination "{ps_app_dir}\\version.txt" -Force
}}
if (Test-Path "{ps_exe}") {{
    Start-Process -FilePath "{ps_exe}"
}}
Remove-Item -Path "{ps_zip}" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "{ps_sha}" -Force -ErrorAction SilentlyContinue
Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
    with open(ps_script, "w", encoding="utf-8-sig") as f:
        f.write(commands)


def install_update_headless(app_dir, release=None):
    """
    Скачивает zip+sha256, проверяет сумму, запускает PowerShell-установщик.
    Без Tk. Возвращает dict: ok / error / restarting.
    """
    if release is None:
        release = fetch_latest_release()
    if not release:
        return {
            "ok": False,
            "error": "Не удалось получить данные о релизе. Проверьте интернет.",
        }

    zip_asset = find_release_asset(release, ZIP_FILENAME)
    sha_asset = find_release_asset(release, SHA256_FILENAME)
    if sha_asset is None:
        sha_asset = find_release_asset(release, "SHA256SUMS")

    if not zip_asset or not _asset_download_url(zip_asset):
        return {"ok": False, "error": f"В релизе нет файла {ZIP_FILENAME}."}

    if not sha_asset or not _asset_download_url(sha_asset):
        return {
            "ok": False,
            "error": "В релизе нет контрольной суммы (*.sha256). Обновление отменено.",
        }

    tmp_dir = tempfile.gettempdir()
    zip_path = os.path.join(tmp_dir, ZIP_FILENAME)
    sha_path = os.path.join(tmp_dir, SHA256_FILENAME)

    try:
        if not download_with_retries(_asset_download_url(zip_asset), zip_path):
            return {
                "ok": False,
                "error": "Не удалось скачать обновление после нескольких попыток.",
            }

        if not download_with_retries(
            _asset_download_url(sha_asset), sha_path, max_retries=3
        ):
            _safe_remove(zip_path)
            return {
                "ok": False,
                "error": "Не удалось скачать файл контрольной суммы.",
            }

        with open(sha_path, "r", encoding="utf-8", errors="ignore") as f:
            expected = parse_sha256_text(f.read())
        if not expected:
            _safe_remove(zip_path)
            _safe_remove(sha_path)
            return {
                "ok": False,
                "error": "Файл контрольной суммы повреждён или имеет неизвестный формат.",
            }

        actual = compute_sha256(zip_path)
        if actual != expected:
            _log(f"SHA-256 mismatch: expected={expected}, actual={actual}")
            _safe_remove(zip_path)
            _safe_remove(sha_path)
            return {
                "ok": False,
                "error": "Контрольная сумма архива не совпала. Обновление отменено.",
            }

        _log(f"SHA-256 OK: {actual}")
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, UnicodeError) as e:
        _safe_remove(zip_path)
        _safe_remove(sha_path)
        return {"ok": False, "error": f"Сбой при проверке обновления: {e}"}

    if sys.platform != "win32":
        return {
            "ok": False,
            "error": "Автоустановка доступна только на Windows. Откройте страницу релиза вручную.",
            "html_url": release.get("html_url"),
            "verified": True,
            "sha256": actual,
        }

    ps_script = os.path.join(tmp_dir, "update_plan.ps1")
    write_update_powershell_script(ps_script, app_dir, zip_path, sha_path)

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps_script],
            creationflags=creationflags,
        )
    except (OSError, ValueError) as e:
        return {"ok": False, "error": f"Не удалось запустить установщик: {e}"}

    return {"ok": True, "restarting": True, "sha256": actual}


def perform_update(app_dir, release=None):
    result = install_update_headless(app_dir, release=release)
    if not result.get("ok"):
        messagebox.showerror(
            "Ошибка обновления",
            result.get("error") or "Неизвестная ошибка обновления.",
        )
        return
    # Установщик ждёт выхода процесса — как и раньше.
    sys.exit(0)


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def check_for_updates(current_version_str, silent_if_updated=False):
    """
    Проверяет наличие новой версии на GitHub.
    При silent_if_updated=True не показывает окно, если версия актуальна.
    """
    release = fetch_latest_release()
    if not release:
        if not silent_if_updated:
            messagebox.showinfo(
                "Проверка обновлений",
                "Не удалось проверить обновления.\nПроверьте интернет-соединение.",
            )
        return

    latest_tag = release.get("tag_name")
    latest_version = parse_version(latest_tag)
    current_version = parse_version(current_version_str)

    _log(
        f"Сравнение: локальная {current_version_str} ({current_version}), "
        f"последняя {latest_tag} ({latest_version})"
    )

    if latest_version > current_version:
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Вышла новая версия {latest_tag}!\n"
            f"Текущая версия: v{current_version_str}\n\n"
            "Хотите скачать и установить обновление сейчас?\n"
            "(будет выполнена проверка SHA-256)",
        )
        if answer:
            perform_update(get_base_dir(), release=release)
        root.destroy()
    else:
        _log("Обновлений нет (версии равны или локальная новее).")
        if not silent_if_updated:
            messagebox.showinfo(
                "Проверка обновлений", "У вас установлена последняя версия."
            )
