"""
Модуль автообновления: проверка, скачивание и установка новой версии.

Защита:
- TLS с проверкой сертификатов (certifi / системное хранилище)
- проверка SHA-256 архива по файлу *.sha256 рядом с релизом на GitHub
- загрузка только с доверенных URL GitHub репозитория
- установка через cmd + tar (без PowerShell Bypass)
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
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import messagebox

GITHUB_OWNER = "Dmitrii-Salikhov"
GITHUB_REPO = f"{GITHUB_OWNER}/Operacionnii_Plan"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ZIP_FILENAME = "PlanOperaciy-Windows.zip"
SHA256_FILENAME = f"{ZIP_FILENAME}.sha256"
USER_AGENT = "PlanOperaciy-Updater"
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)


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


def is_trusted_download_url(url):
    """Разрешены только https-ссылки на артефакты нашего GitHub-репозитория."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_DOWNLOAD_HOSTS:
        return False
    if host == "github.com":
        path = parsed.path or ""
        return path.startswith(f"/{GITHUB_REPO}/")
    return True


def is_trusted_release_page_url(url):
    """Страница релиза на GitHub нашего репозитория."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if (parsed.hostname or "").lower() != "github.com":
        return False
    path = parsed.path or ""
    return path.startswith(f"/{GITHUB_REPO}/releases")


def _http_get(url, timeout=15):
    """GET только с API/ассетов нашего GitHub-репозитория."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as e:
        raise ValueError(f"Untrusted URL blocked: {url}") from e
    if parsed.scheme != "https":
        raise ValueError(f"Untrusted URL blocked: {url}")
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    api_ok = host == "api.github.com" and path.startswith(f"/repos/{GITHUB_REPO}/")
    if not api_ok and not is_trusted_download_url(url):
        raise ValueError(f"Untrusted URL blocked: {url}")
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
    url = asset.get("browser_download_url")
    if url and not is_trusted_download_url(url):
        _log(f"Отклонён недоверенный URL ассета: {url}")
        return None
    return url


def write_update_cmd_script(cmd_script, app_dir, zip_path, extra_cleanup=None):
    """
    Пишет .cmd установщик: ждёт выхода приложения, распаковывает zip через tar,
    перезапускает exe. Без PowerShell Bypass.
    """
    cleanup = list(extra_cleanup or [])

    def set_var(name, value):
        safe = str(value).replace('"', "")
        return f'set "{name}={safe}"'

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal",
        set_var("APPDIR", app_dir),
        set_var("ZIP", zip_path),
        "taskkill /F /IM PlanOperaciy.exe /T >nul 2>&1",
        "taskkill /F /IM PlanOperaciyBackend.exe /T >nul 2>&1",
        "set /a i=0",
        ":waitloop",
        'tasklist /FI "IMAGENAME eq PlanOperaciy.exe" | find /I "PlanOperaciy.exe" >nul',
        "if errorlevel 1 goto extract",
        "timeout /t 1 /nobreak >nul",
        "set /a i+=1",
        "if %i% LSS 80 goto waitloop",
        ":extract",
        'tar -xf "%ZIP%" -C "%APPDIR%"',
        'if exist "%APPDIR%\\_internal\\version.txt" (',
        '  move /Y "%APPDIR%\\_internal\\version.txt" "%APPDIR%\\version.txt" >nul',
        ")",
        'if exist "%APPDIR%\\PlanOperaciy.exe" (',
        '  start "" "%APPDIR%\\PlanOperaciy.exe"',
        ")",
        'del /F /Q "%ZIP%" >nul 2>&1',
    ]
    for path in cleanup:
        safe = str(path).replace('"', "")
        lines.append(f'del /F /Q "{safe}" >nul 2>&1')
    lines.append('del /F /Q "%~f0" >nul 2>&1')
    text = "\r\n".join(lines) + "\r\n"
    with open(cmd_script, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)


def write_update_powershell_script(ps_script, app_dir, zip_path, sha_path):
    """Совместимость со старыми тестами: пишет cmd рядом и зеркало логики."""
    cmd_path = os.path.splitext(ps_script)[0] + ".cmd"
    write_update_cmd_script(cmd_path, app_dir, zip_path, extra_cleanup=[sha_path])
    # Также оставить .ps1-заглушку без Bypass — вызывает cmd.
    body = (
        f'$ErrorActionPreference = "Stop"\n'
        f'& cmd.exe /c "{cmd_path.replace(chr(34), "")}"\n'
    )
    with open(ps_script, "w", encoding="utf-8-sig") as f:
        f.write(body)


def install_update_headless(app_dir, release=None):
    """
    Скачивает zip + sha256, проверяет сумму, запускает cmd-установщик.
    Без Tk. Возвращает dict: ok / error / restarting.
    """
    if release is None:
        release = fetch_latest_release()
    if not release:
        return {
            "ok": False,
            "error": "Не удалось получить данные о релизе. Проверьте интернет.",
        }

    html_url = release.get("html_url")
    if html_url and not is_trusted_release_page_url(html_url):
        return {"ok": False, "error": "Недоверенный URL страницы релиза."}

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
            "html_url": html_url if is_trusted_release_page_url(html_url or "") else None,
            "verified": True,
            "sha256": actual,
        }

    cmd_script = os.path.join(tmp_dir, "update_plan.cmd")
    write_update_cmd_script(cmd_script, app_dir, zip_path, extra_cleanup=[sha_path])

    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        subprocess.Popen(
            ["cmd.exe", "/c", cmd_script],
            creationflags=creationflags,
            close_fds=True,
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
