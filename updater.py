"""
Модуль автообновления: проверка, скачивание и установка новой версии.
Версия 1.0.27 – добавлено информационное окно при ручной проверке,
устойчивое скачивание, правильное расположение version.txt.
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

def get_base_dir():
    """Возвращает папку, где находится исполняемый файл (exe или .py)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

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
            log_path = os.path.join(get_base_dir(), 'update.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"Получен тег: {tag}\n")
            return tag
    except Exception as e:
        try:
            log_path = os.path.join(get_base_dir(), 'update.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"Ошибка проверки обновлений: {e}\n")
        except:
            pass
        return None

def parse_version(tag):
    """Преобразует тег 'v1.2.3' или '1.2.3' в кортеж чисел (1, 2, 3)."""
    if tag:
        v = tag.lstrip('v')
        parts = v.split('.')
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0)

def read_current_version():
    """Читает локальный файл version.txt. Возвращает строку версии."""
    try:
        version_path = os.path.join(get_base_dir(), 'version.txt')
        with open(version_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

def download_with_retries(url, dest_path, max_retries=7, timeout=60):
    """
    Скачивает файл с экспоненциальной задержкой между попытками.
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
            log_path = os.path.join(get_base_dir(), 'update.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"Ошибка скачивания (попытка {attempt}/{max_retries}): {e}\n")
            if attempt == max_retries:
                return False
            # Экспоненциальная задержка: 3, 6, 12, 24, ...
            wait_seconds = 3 * (2 ** (attempt - 1))
            time.sleep(wait_seconds)
    return False

def perform_update(app_dir):
    download_url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{ZIP_FILENAME}"
    tmp_dir = tempfile.gettempdir()
    zip_path = os.path.join(tmp_dir, ZIP_FILENAME)

    # Показываем окно прогресса
    progress_win = tk.Toplevel()
    progress_win.title("Обновление")
    progress_win.geometry("300x100")
    progress_win.resizable(False, False)
    tk.Label(progress_win, text="Идёт обновление…\nПожалуйста, не выключайте компьютер.",
             font=('Segoe UI', 10)).pack(expand=True, pady=15)
    progress_win.update()

    if not download_with_retries(download_url, zip_path):
        progress_win.destroy()
        messagebox.showerror("Ошибка обновления",
                             "Не удалось скачать обновление после нескольких попыток.\n"
                             "Проверьте интернет-соединение и повторите позже.")
        return

    # PowerShell-скрипт
    ps_script = os.path.join(tmp_dir, "update_plan.ps1")
    ps_app_dir = app_dir.replace('\\', '\\\\')
    ps_zip = zip_path.replace('\\', '\\\\')
    ps_exe = os.path.join(app_dir, 'PlanOperaciy.exe').replace('\\', '\\\\')

    commands = f"""
$timeout = 50
$proc = Get-Process -Name "PlanOperaciy" -ErrorAction SilentlyContinue
if ($proc) {{
    $proc | Stop-Process -Force
    for ($i=0; $i -lt $timeout; $i++) {{
        if (-not (Get-Process -Name "PlanOperaciy" -ErrorAction SilentlyContinue)) {{
            break
        }}
        Start-Sleep -Milliseconds 100
    }}
}}
Expand-Archive -Path "{ps_zip}" -DestinationPath "{ps_app_dir}" -Force
if (Test-Path "{ps_app_dir}\\_internal\\version.txt") {{
    Move-Item -Path "{ps_app_dir}\\_internal\\version.txt" -Destination "{ps_app_dir}\\version.txt" -Force
}}
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
        progress_win.destroy()
        messagebox.showerror("Ошибка обновления", f"Не удалось запустить установщик:\n{e}")
        return

    sys.exit(0)

def check_for_updates(current_version_str, silent_if_updated=False):
    """
    Проверяет наличие новой версии на GitHub.
    При silent_if_updated=True (автоматическая проверка) не показывает окно, если версия актуальна.
    При ручной проверке (silent_if_updated=False) всегда показывает результат.
    """
    latest_tag = get_latest_version()
    if not latest_tag:
        if not silent_if_updated:
            messagebox.showinfo("Проверка обновлений", "Не удалось проверить обновления.\nПроверьте интернет-соединение.")
        return

    latest_version = parse_version(latest_tag)
    current_version = parse_version(current_version_str)

    log_path = os.path.join(get_base_dir(), 'update.log')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"Сравнение: локальная {current_version_str} ({current_version}), последняя {latest_tag} ({latest_version})\n")

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
            app_dir = get_base_dir()
            perform_update(app_dir)
        root.destroy()
    else:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write("Обновлений нет (версии равны или локальная новее).\n")
        if not silent_if_updated:
            messagebox.showinfo("Проверка обновлений", "У вас установлена последняя версия.")