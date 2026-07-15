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

_DEFAULT_RULES: Dict[str, Any] = {
    "tonsil_keywords": ["тонзил", "т/э", "т-э", "т/эктом", "тэ"],
    "narcosis_closed_phrases": ["закрыто для наркоза", "зарыто для наркоза"],
    "narcosis_closed_fuzzy": "закрыто для наркоза",
    "narcosis_closed_fuzzy_threshold": 85,
    "generalochka_keywords": ["генералочка"],
    "holiday_keywords": ["праздник", "выходной", "каникулы"],
    "service_keywords": ["для со", "каникулы", "генералочка"],
}

_rules: Optional[Dict[str, Any]] = None


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


def _contains_any(text: str, keywords: List[str]) -> bool:
    low = (text or "").lower()
    return any(kw.lower() in low for kw in keywords)


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
    закрыто для наркоза (fuzzy) и т.п.
    """
    low = (title or "").lower()
    rules = get_rules()
    if _contains_any(low, rules.get("service_keywords", [])):
        return True
    if is_narcosis_closed(title):
        return True
    if is_holiday_or_day_off(title):
        return True
    return False


def classify_calendar_title(title: str) -> Optional[str]:
    """
    Тип служебного события для разбора календаря:
    'narcosis_closed' | 'generalochka' | 'holiday' | 'service' | None (пациент).
    Порядок: narcosis → generalochka → holiday → прочий service.
    """
    if is_narcosis_closed(title):
        return "narcosis_closed"
    if is_generalochka(title):
        return "generalochka"
    if is_holiday_or_day_off(title):
        return "holiday"
    if is_service_event(title):
        return "service"
    return None


# Загрузка при импорте
load_room_rules()
