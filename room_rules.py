"""
Единые правила операционных и служебных событий.

Ключевые слова загружаются из room_rules.json — без дублирования по модулям.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from fuzzywuzzy import fuzz

from patient_parser import _resolve_resource_path

DEFAULT_RULES_FILE = "room_rules.json"
DEFAULT_SERVICE_NOTE_ALIASES_FILE = "service_note_aliases.json"

_DEFAULT_RULES: Dict[str, Any] = {
    "tonsil_keywords": ["тонзил", "т/э", "т-э", "т/эктом", "тэ"],
    "narcosis_closed_phrases": ["закрыто для наркоза", "зарыто для наркоза"],
    "narcosis_closed_fuzzy": "закрыто для наркоза",
    "narcosis_closed_fuzzy_threshold": 85,
    "generalochka_keywords": ["генералочка"],
    "holiday_keywords": ["праздник", "выходной", "каникулы"],
    "service_keywords": ["для со", "каникулы", "генералочка"],
    # Пометки в календаре → столбец «Примечания» (короткие — по границам слов)
    "note_keywords": ["перенос", "джабраил", "да"],
}

_rules: Optional[Dict[str, Any]] = None
_service_note_aliases: Optional[Dict[str, str]] = None


def load_room_rules(path: Optional[str] = None) -> Dict[str, Any]:
    """Загружает правила из JSON (или defaults)."""
    global _rules
    file_path = path or _resolve_resource_path(DEFAULT_RULES_FILE)
    data = dict(_DEFAULT_RULES)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data.update(loaded)
    _rules = data
    return data


def get_rules() -> Dict[str, Any]:
    if _rules is None:
        return load_room_rules()
    return _rules


def reload_room_rules(path: Optional[str] = None) -> Dict[str, Any]:
    """Принудительная перезагрузка (для тестов)."""
    global _rules
    _rules = None
    return load_room_rules(path)

def load_service_note_aliases(path: Optional[str] = None) -> Dict[str, str]:
    """Загружает алиасы для служебных пометок (сырой токен → отображение)."""
    global _service_note_aliases
    file_path = path or _resolve_resource_path(DEFAULT_SERVICE_NOTE_ALIASES_FILE)
    if not os.path.exists(file_path):
        _service_note_aliases = {}
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        _service_note_aliases = {}
        return {}
    # Ключ нормализуем в lowercase.
    _service_note_aliases = {str(k).lower(): str(v) for k, v in raw.items() if str(k).strip()}
    return _service_note_aliases


def get_service_note_aliases() -> Dict[str, str]:
    """Возвращает алиасы служебных пометок (например, что именно даёт «дж»)."""
    global _service_note_aliases
    if _service_note_aliases is None:
        return load_service_note_aliases()
    return _service_note_aliases


def save_service_note_alias(raw_token: str, display_value: str, path: Optional[str] = None) -> None:
    """Сохраняет алиас для служебной пометки."""
    raw_token = (raw_token or "").strip().lower()
    display_value = (display_value or "").strip()
    if not raw_token or not display_value:
        return
    file_path = path or _resolve_resource_path(DEFAULT_SERVICE_NOTE_ALIASES_FILE)
    data = get_service_note_aliases().copy()
    data[raw_token] = display_value
    # Гарантируем директорию (на случай необычного окружения).
    parent_dir = os.path.dirname(file_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Обновим кеш.
    global _service_note_aliases
    _service_note_aliases = data


def _contains_any(text: str, keywords: List[str]) -> bool:
    low = (text or "").lower()
    return any(kw.lower() in low for kw in keywords)


def _keyword_pattern(keyword: str) -> re.Pattern:
    """Короткие маркеры (≤3) — только целые слова, длинные — подстрока."""
    k = keyword.lower()
    if len(k) <= 3:
        return re.compile(
            r"(?<![а-яёa-z0-9])" + re.escape(k) + r"(?![а-яёa-z0-9])",
            re.IGNORECASE,
        )
    return re.compile(re.escape(k), re.IGNORECASE)


def is_tonsillectomy(text: str) -> bool:
    """Тонзилэктомия / т/э / тэ и т.п. в тексте диагноза."""
    low = (text or "").lower()
    rules = get_rules()
    for kw in rules.get("tonsil_keywords", []):
        k = kw.lower()
        if len(k) <= 2:
            if re.search(r"(?<![а-яёa-z0-9])" + re.escape(k) + r"(?![а-яёa-z0-9])", low):
                return True
        elif k in low:
            return True
    return False


def extract_service_notes(text: str) -> tuple[str, str]:
    """
    Вырезает служебные пометки (перенос, ДА, Джабраил, …) из текста.
    Возвращает (очищенный_текст, примечания через «; »).
    """
    raw = text or ""
    rules = get_rules()
    keywords = list(rules.get("note_keywords") or [])
    # Длинные фразы раньше коротких («перенос» до «да»)
    keywords.sort(key=lambda k: (-len(k), k.lower()))

    found: List[str] = []
    cleaned = raw
    aliases = get_service_note_aliases()
    for kw in keywords:
        pat = _keyword_pattern(kw)

        def _collect(match: re.Match, _kw=kw) -> str:
            token = match.group(0).strip()
            if _kw.lower() == "да":
                display = "ДА"
            elif _kw.lower() in aliases:
                # Пользовательская настройка: что именно должно подставляться для «дж».
                display = aliases[_kw.lower()]
            elif token.isupper() or token[:1].isupper():
                display = token
            else:
                display = token.capitalize() if len(token) > 2 else token.upper()
            if display not in found:
                found.append(display)
            return " "

        cleaned = pat.sub(_collect, cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t,.;:-")
    notes = "; ".join(found)
    return cleaned, notes


def is_pure_note_event(title: str) -> bool:
    """Событие состоит только из служебных пометок (и времени/пунктуации)."""
    cleaned, notes = extract_service_notes(title)
    if not notes:
        return False
    leftover = re.sub(r"[\s\d.:/\-,;!?]+", "", cleaned)
    return not leftover


def is_narcosis_closed(title: str) -> bool:
    """Событие «закрыто для наркоза» (включая опечатки)."""
    low = (title or "").lower()
    rules = get_rules()
    if _contains_any(low, rules.get("narcosis_closed_phrases", [])):
        return True
    fuzzy_phrase = rules.get("narcosis_closed_fuzzy", "закрыто для наркоза")
    threshold = int(rules.get("narcosis_closed_fuzzy_threshold", 85))
    return fuzz.partial_ratio(fuzzy_phrase, low) >= threshold


def is_generalochka(title: str) -> bool:
    return _contains_any(title or "", get_rules().get("generalochka_keywords", []))


def is_holiday_or_day_off(title: str) -> bool:
    return _contains_any(title or "", get_rules().get("holiday_keywords", []))


def is_service_event(title: str) -> bool:
    """
    Служебное событие (не пациент): для СО, каникулы, генералочка,
    закрыто для наркоза (fuzzy), чистые пометки (перенос / ДА / …) и т.п.
    """
    low = (title or "").lower()
    rules = get_rules()
    if _contains_any(low, rules.get("service_keywords", [])):
        return True
    if is_narcosis_closed(title):
        return True
    if is_holiday_or_day_off(title):
        return True
    if is_pure_note_event(title):
        return True
    return False


def classify_calendar_title(title: str) -> Optional[str]:
    """
    Тип служебного события для разбора календаря:
    'narcosis_closed' | 'generalochka' | 'holiday' | 'service_note' | 'service' | None.
    Порядок: narcosis → generalochka → holiday → пометка → прочий service.
    """
    if re.search(r"место\s+для\s+перенос", (title or ""), flags=re.IGNORECASE):
        # Это не пациент, а пометка для ближайшей пересадки/переноса места.
        # В «Примечания» уходит слово «Перенос».
        return "service_note"
    if is_narcosis_closed(title):
        return "narcosis_closed"
    if is_generalochka(title):
        return "generalochka"
    if is_holiday_or_day_off(title):
        return "holiday"
    if is_pure_note_event(title):
        return "service_note"
    if is_service_event(title):
        return "service"
    return None


# Загрузка при импорте
load_room_rules()
load_service_note_aliases()
