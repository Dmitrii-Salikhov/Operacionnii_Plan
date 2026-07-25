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

# Плейсхолдеры из старых calendars.example.json — не слать в Google API.
_PLACEHOLDER_FRAGMENTS = (
    "your-first-calendar",
    "your-second-calendar",
    "example@example",
)


def is_placeholder_calendar_id(cal_id: str) -> bool:
    """True для пустых и шаблонных ID из example."""
    low = str(cal_id or "").strip().lower()
    if not low:
        return True
    return any(fragment in low for fragment in _PLACEHOLDER_FRAGMENTS)


def _normalize_calendar_ids(raw_ids) -> List[str]:
    ids = [str(x).strip() for x in (raw_ids or []) if str(x).strip()]
    real = [cal_id for cal_id in ids if not is_placeholder_calendar_id(cal_id)]
    skipped = len(ids) - len(real)
    if skipped:
        logger.warning(
            "Пропущено %s шаблонных ID календаря — заполните %s реальными email/ID",
            skipped,
            CALENDARS_FILE,
        )
    return real


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
            ids = _normalize_calendar_ids(ids)
            # calendars.json exists → respect empty list (user cleared IDs)
            if path == CALENDARS_FILE:
                return ids
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


def save_calendar_ids(calendar_ids: List[str], provider: str | None = None) -> List[str]:
    """
    Пишет calendars.json с нормализованным списком ID.
    Возвращает сохранённый (отфильтрованный) список.
    """
    existing = _read_config_dict()
    prov = (provider or existing.get("provider") or DEFAULT_PROVIDER)
    prov = str(prov).strip().lower() or DEFAULT_PROVIDER
    if prov not in KNOWN_PROVIDERS:
        raise ValueError(f"Неизвестный provider: {prov}")

    cleaned = _normalize_calendar_ids(calendar_ids)
    # Allow saving empty list (user clearing) but warn via return
    raw_ids = [str(x).strip() for x in (calendar_ids or []) if str(x).strip()]
    placeholders = [x for x in raw_ids if is_placeholder_calendar_id(x)]
    if placeholders:
        logger.warning("Отброшены шаблонные ID: %s", placeholders)

    payload: Dict[str, Any] = {
        "provider": prov,
        "calendar_ids": cleaned,
        "_comment": (
            "Укажите email/ID календарей Google. "
            "Файл рядом с программой; образец — calendars.example.json."
        ),
    }
    with open(CALENDARS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return cleaned
