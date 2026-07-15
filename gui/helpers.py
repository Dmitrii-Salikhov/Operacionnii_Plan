"""Вспомогательные функции GUI: конфиг, пути, открытие папок."""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime

from constants import CONFIG_FILE, OLD_CONFIG_FILE

logger = logging.getLogger("plan_generator")


def resource_path(relative_path):
    """Абсолютный путь к ресурсу (PyInstaller и разработка)."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_config():
    config = {"last_dir": "", "last_monday": None}
    if os.path.exists(OLD_CONFIG_FILE):
        try:
            with open(OLD_CONFIG_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            config["last_dir"] = old_data.get("last_dir", "")
            os.remove(OLD_CONFIG_FILE)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Не удалось прочитать/мигрировать %s: %s", OLD_CONFIG_FILE, e)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config.update(data)
            else:
                logger.warning("%s имеет неожиданный формат (не объект)", CONFIG_FILE)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Не удалось прочитать %s: %s", CONFIG_FILE, e)
    if config.get("last_monday"):
        try:
            config["last_monday"] = datetime.strptime(
                config["last_monday"], "%Y-%m-%d"
            ).date()
        except (TypeError, ValueError) as e:
            logger.warning("Некорректная last_monday в конфиге: %s", e)
            config["last_monday"] = None
    else:
        config["last_monday"] = None
    return config


def save_config(last_dir=None, last_monday=None):
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config = data
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Не удалось прочитать %s перед сохранением: %s", CONFIG_FILE, e)
    if last_dir is not None:
        config["last_dir"] = last_dir
    if last_monday is not None:
        config["last_monday"] = (
            last_monday.isoformat()
            if hasattr(last_monday, "isoformat")
            else last_monday
        )
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)


def open_folder(path):
    if sys.platform == "darwin":
        subprocess.call(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.call(["xdg-open", path])
