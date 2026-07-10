"""
Модуль автообновления: проверка, скачивание и установка новой версии.
"""
import json
import os
import sys
import tempfile
import urllib.request
import subprocess
import tkinter as tk
from tkinter import messagebox

GITHUB_REPO = "Dmitrii-Salikhov/Operacionnii_Plan"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ZIP_FILENAME = "PlanOperaciy-Windows.zip"

def get_latest_version():
    """Возвращает строку с последней версией (например, 'v1.0.1') или None при ошибке."""
    try:
        with urllib.request.urlopen(API_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            tag = data.get("tag_name")
            return tag
    except Exception as e:
        # Записываем ошибку в update.log рядом с exe
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

def perform_update(app_dir):
    """
    Скачивает последний релизный zip, создаёт PowerShell-скрипт для замены файлов
    и перезапуска, запускает его и завершает текущий процесс.
    """
    download_url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{ZIP_FILENAME}"
    tmp_dir = tempfile.gettempdir()
    zip_path = os.path.join(tmp_dir, ZIP_FILENAME)

    try:
        # Скачиваем архив
        print("Скачивание обновления...")
        urllib.request.urlretrieve(download_url, zip_path)
    except Exception as e:
        messagebox.showerror("Ошибка обновления", f"Не удалось скачать обновление:\n{e}")
        return

    # Создаём скрипт PowerShell для замены файлов и перезапуска
    ps_script = os.path.join(tmp_dir, "update_plan.ps1")
    # Экранируем пути для PowerShell
    ps_app_dir = app_dir.replace('\\', '\\\\')
    ps_zip = zip_path.replace('\\', '\\\\')
    ps_exe = os.path.join(app_dir, 'PlanOperaciy.exe').replace('\\', '\\\\')

    commands = f"""
Start-Sleep -Seconds 2
# Останавливаем старый процесс, если ещё висит
Get-Process -Name "PlanOperaciy" -ErrorAction SilentlyContinue | Stop-Process -Force
# Распаковываем архив с заменой
Expand-Archive -Path "{ps_zip}" -DestinationPath "{ps_app_dir}" -Force
# Запускаем новую версию
Start-Process -FilePath "{ps_exe}"
# Удаляем скачанный архив
Remove-Item -Path "{ps_zip}" -Force
"""
    with open(ps_script, 'w', encoding='ascii') as f:
        f.write(commands)

    # Запускаем скрипт и выходим
    try:
        subprocess.Popen(
            ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except Exception as e:
        messagebox.showerror("Ошибка обновления", f"Не удалось запустить установщик:\n{e}")
        return

    # Закрываем текущее приложение
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
            # Определяем папку, в которой находится исполняемый файл
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            perform_update(app_dir)
        root.destroy()