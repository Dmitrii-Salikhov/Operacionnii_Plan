"""
Модуль автообновления: проверка, скачивание и установка новой версии.
"""
import json
import os
import sys
import tempfile
import urllib.request
import ssl
import subprocess
import tkinter as tk
from tkinter import messagebox
import time

GITHUB_REPO = "Dmitrii-Salikhov/Operacionnii_Plan"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ZIP_FILENAME = "PlanOperaciy-Windows.zip"

def _ssl_context():
    """Создаёт SSL-контекст без проверки сертификата (только для GitHub API)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_latest_version():
    """Возвращает строку с последней версией (например, 'v1.0.1') или None при ошибке."""
    try:
        req = urllib.request.Request(API_URL, headers={'User-Agent': 'PlanOperaciy-Updater'})
        with urllib.request.urlopen(req, timeout=5, context=_ssl_context()) as response:
            data = json.loads(response.read().decode())
            tag = data.get("tag_name")
            # Логируем успех
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            with open(os.path.join(base_dir, 'update.log'), 'a', encoding='utf-8') as f:
                f.write(f"Получен тег: {tag}\n")
            return tag
    except Exception as e:
        # Логируем ошибку
        try:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            with open(os.path.join(base_dir, 'update.log'), 'a', encoding='utf-8') as f:
                f.write(f"Ошибка проверки обновлений: {e}\n")
        except:
            pass
        return None

def parse_version(tag):
    """Преобразует тег 'v1.2.3' в кортеж чисел (1, 2, 3)."""
    if tag and tag.startswith('v'):
        parts = tag[1:].split('.')
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0)

def read_current_version():
    """Читает локальный файл version.txt. Возвращает строку версии."""
    try:
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        with open(os.path.join(base_dir, 'version.txt'), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

def download_with_retries(url, dest_path, max_retries=3, timeout=60):
    """
    Скачивает файл с повторными попытками при сетевых ошибках.
    Возвращает True в случае успеха, иначе False.
    """
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'PlanOperaciy-Updater'})
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
                with open(dest_path, 'wb') as out_file:
                    out_file.write(resp.read())
            return True
        except Exception as e:
            if attempt == max_retries:
                # Логируем последнюю ошибку
                try:
                    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                    with open(os.path.join(base_dir, 'update.log'), 'a', encoding='utf-8') as f:
                        f.write(f"Ошибка скачивания (попытка {attempt}): {e}\n")
                except:
                    pass
                return False
            else:
                # Ждём перед повтором
                time.sleep(2 * attempt)
    return False

def perform_update(app_dir):
    """
    Скачивает последний релизный zip, создаёт PowerShell-скрипт для замены файлов
    и перезапуска, запускает его и завершает текущий процесс.
    """
    download_url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{ZIP_FILENAME}"
    tmp_dir = tempfile.gettempdir()
    zip_path = os.path.join(tmp_dir, ZIP_FILENAME)

    # Скачиваем с повторами
    if not download_with_retries(download_url, zip_path):
        messagebox.showerror("Ошибка обновления", "Не удалось скачать обновление после нескольких попыток.\nПроверьте интернет-соединение.")
        return

    # Создаём скрипт PowerShell для замены файлов и перезапуска
    ps_script = os.path.join(tmp_dir, "update_plan.ps1")
    ps_app_dir = app_dir.replace('\\', '\\\\')
    ps_zip = zip_path.replace('\\', '\\\\')
    ps_exe = os.path.join(app_dir, 'PlanOperaciy.exe').replace('\\', '\\\\')

    commands = f"""
Start-Sleep -Seconds 2
Get-Process -Name "PlanOperaciy" -ErrorAction SilentlyContinue | Stop-Process -Force
Expand-Archive -Path "{ps_zip}" -DestinationPath "{ps_app_dir}" -Force
Start-Process -FilePath "{ps_exe}"
Remove-Item -Path "{ps_zip}" -Force
"""
    with open(ps_script, 'w', encoding='ascii') as f:
        f.write(commands)

    try:
        subprocess.Popen(
            ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except Exception as e:
        messagebox.showerror("Ошибка обновления", f"Не удалось запустить установщик:\n{e}")
        return

    sys.exit(0)

def check_for_updates(current_version_str):
    """
    Проверяет наличие новой версии на GitHub.
    Если есть обновление, показывает диалог. При согласии запускает полное обновление.
    """
    latest_tag = get_latest_version()
    if not latest_tag:
        return

    latest_version = parse_version(latest_tag)
    current_version = parse_version(current_version_str)

    if latest_version > current_version:
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Вышла новая версия {latest_tag}!\n"
            f"Текущая версия: v{current_version_str}\n\n"
            "Хотите скачать и установить обновление сейчас?"
        )
        if answer:
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            perform_update(app_dir)
        root.destroy()