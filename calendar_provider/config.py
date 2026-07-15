"""Конфиг календарей: provider + список ID (независимо от бэкенда)."""

import json
import logging
import os
from typing import Any, Dict, List

from constants import (
    CALENDARS_EXAMPLE_FILE,
    CALENDARS_FILE,
)

logger = logging.getLogger("plan_generator")

# Запасные ID только если нет calendars.json / calendars.example.json
DEFAULT_CALENDAR_IDS: List[str] = []
DEFAULT_PROVIDER = "google"

# Известные провайдеры. Новый адаптер — добавить сюда и в factory.
KNOWN_PROVIDERS = frozenset({"google"})


def _read_config_dict() -> Dict[str, Any]:
    """Читает первый доступный JSON (calendars.json, иначе example)."""
    for path in (CALENDARS_FILE, CALENDARS_EXAMPLE_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {"calendar_ids": data, "provider": DEFAULT_PROVIDER}
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Не удалось прочитать календари из %s: %s", path, e)
            continue
    return {}


def load_provider() -> str:
    """Имя провайдера из calendars.json (по умолчанию google)."""
    data = _read_config_dict()
    provider = str(data.get("provider") or DEFAULT_PROVIDER).strip().lower()
    return provider or DEFAULT_PROVIDER


def load_calendar_ids() -> List[str]:
    """Читает список календарей из calendars.json (или из example)."""
    for path in (CALENDARS_FILE, CALENDARS_EXAMPLE_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                ids = data.get("calendar_ids") or data.get("calendars") or []
            elif isinstance(data, list):
                ids = data
            else:
                continue
            ids = [str(x).strip() for x in ids if str(x).strip()]
            if ids:
                return ids
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Не удалось прочитать календари из %s: %s", path, e)
            continue
    return list(DEFAULT_CALENDAR_IDS)


def ensure_calendars_config() -> List[str]:
    """
    Если calendars.json отсутствует, копирует пример (если есть).
    Возвращает список ID или пустой список.
    """
    if not os.path.exists(CALENDARS_FILE) and os.path.exists(CALENDARS_EXAMPLE_FILE):
        try:
            with open(CALENDARS_EXAMPLE_FILE, "r", encoding="utf-8") as src:
                raw = src.read()
            with open(CALENDARS_FILE, "w", encoding="utf-8") as dst:
                dst.write(raw)
        except OSError as e:
            logger.warning("Не удалось создать %s из example: %s", CALENDARS_FILE, e)
    return load_calendar_ids()
