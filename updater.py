"""
Модуль проверки обновлений через GitHub Releases.
Использует GitHub API для получения последнего релиза и сравнения версий.
"""
import json
import urllib.request
import tkinter as tk
from tkinter import messagebox
import webbrowser

GITHUB_REPO = "Dmitrii-Salikhov/Operacionnii_Plan"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def get_latest_version():
    """
    Возвращает строку с последней версией (например, 'v1.0.1') или None при ошибке.
    """
    try:
        with urllib.request.urlopen(API_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            tag = data.get("tag_name")
            return tag
    except Exception as e:
        # Логируем ошибку, но не мешаем работе приложения
        print(f"Ошибка проверки обновлений: {e}")
        return None

def parse_version(tag):
    """
    Преобразует тег 'v1.2.3' в кортеж чисел (1, 2, 3).
    Если тег не соответствует формату, возвращает (0, 0, 0).
    """
    if tag.startswith('v'):
        parts = tag[1:].split('.')
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0)

def read_current_version():
    """
    Читает локальный файл version.txt (лежит рядом с exe или в текущей папке).
    Возвращает строку версии, например '1.0.0', или '0.0.0' при ошибке.
    """
    import os
    try:
        # Ищем version.txt в директории, где находится скрипт/приложение
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, 'version.txt'), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

def check_for_updates(current_version_str):
    """
    Проверяет наличие новой версии на GitHub.
    Если есть обновление, показывает диалог с предложением скачать.
    current_version_str: строка, например '1.0.0' (из version.txt)
    """
    latest_tag = get_latest_version()
    if not latest_tag:
        return  # Нет интернета или ошибка API — просто продолжаем

    latest_version = parse_version(latest_tag)
    current_version = parse_version(current_version_str)

    if latest_version > current_version:
        # Диалог с вопросом
        root = tk.Tk()
        root.withdraw()  # скрываем главное окно
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Вышла новая версия {latest_tag}!\n"
            f"Текущая версия: v{current_version_str}\n\n"
            "Хотите скачать и установить обновление?"
        )
        if answer:
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
        root.destroy()