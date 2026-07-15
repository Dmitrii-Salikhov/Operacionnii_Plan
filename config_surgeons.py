import json
import os
from typing import Dict, List, Set

SURGEON_CONFIG_FILE = "surgeons.json"

# Значения по умолчанию
DEFAULT_SURGEON_5 = {
    0: "Баганов Д.Г.", 1: "Гасанов М.Т.", 2: "Карибова С.О.",
    3: "Салихов Д.А.", 4: "Гасанов М.Т."
}
DEFAULT_SURGEON_7 = "Доронина Н.С."
DEFAULT_SURGEON_MA = {
    0: "Карибова С.О.", 1: "Баганов Д.Г.", 2: "Гасанов М.Т.",
    3: "Карибова С.О.", 4: "Баганов Д.Г."
}
DEFAULT_FORBIDDEN_MA = ["Салихов Д.А.", "Доронина Н.С."]


def load_surgeons():
    """Загружает расписание хирургов из JSON или возвращает умолчания."""
    if os.path.exists(SURGEON_CONFIG_FILE):
        with open(SURGEON_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        surg5 = {int(k): v for k, v in data.get("SURGEON_5", {}).items()}
        surg7 = data.get("SURGEON_7", DEFAULT_SURGEON_7)
        surgMA = {int(k): v for k, v in data.get("SURGEON_MA", {}).items()}
        forbidden = data.get("FORBIDDEN_MA", DEFAULT_FORBIDDEN_MA)
        return surg5, surg7, surgMA, forbidden
    else:
        save_surgeons(DEFAULT_SURGEON_5, DEFAULT_SURGEON_7, DEFAULT_SURGEON_MA, DEFAULT_FORBIDDEN_MA)
        return DEFAULT_SURGEON_5, DEFAULT_SURGEON_7, DEFAULT_SURGEON_MA, DEFAULT_FORBIDDEN_MA


def save_surgeons(surgeon_5, surgeon_7, surgeon_ma, forbidden_ma):
    """Сохраняет расписание в JSON."""
    data = {
        "SURGEON_5": {str(k): v for k, v in surgeon_5.items()},
        "SURGEON_7": surgeon_7,
        "SURGEON_MA": {str(k): v for k, v in surgeon_ma.items()},
        "FORBIDDEN_MA": forbidden_ma
    }
    with open(SURGEON_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def collect_surgeon_names(
    surgeon_5: Dict[int, str],
    surgeon_7: str,
    surgeon_ma: Dict[int, str],
    forbidden_ma: List[str],
) -> Set[str]:
    """Все уникальные ФИО из текущего расписания и запретов."""
    names: Set[str] = set()
    for value in surgeon_5.values():
        if value:
            names.add(value)
    if surgeon_7:
        names.add(surgeon_7)
    for value in surgeon_ma.values():
        if value:
            names.add(value)
    for value in forbidden_ma or []:
        if value:
            names.add(value)
    return names


def ordered_roster(
    surgeon_5: Dict[int, str],
    surgeon_7: str,
    surgeon_ma: Dict[int, str],
    forbidden_ma: List[str],
) -> List[str]:
    """
    Стабильный порядок кандидатов: сначала М/А по дням, затем №5, затем №7,
    затем остальные по алфавиту.
    """
    ordered: List[str] = []
    for day in range(5):
        name = surgeon_ma.get(day)
        if name and name not in ordered:
            ordered.append(name)
    for day in range(5):
        name = surgeon_5.get(day)
        if name and name not in ordered:
            ordered.append(name)
    if surgeon_7 and surgeon_7 not in ordered:
        ordered.append(surgeon_7)
    for name in sorted(collect_surgeon_names(surgeon_5, surgeon_7, surgeon_ma, forbidden_ma)):
        if name not in ordered:
            ordered.append(name)
    return ordered


def pick_ma_surgeon(
    day: int,
    surgeon_5: Dict[int, str],
    surgeon_7: str,
    surgeon_ma: Dict[int, str],
    forbidden_ma: List[str],
) -> str:
    """
    Хирург М/А на день. Если совпал с №5 — берём следующего из расписания,
    исключая forbidden и конфликтующего.
    """
    assigned = surgeon_ma.get(day, "")
    room5 = surgeon_5.get(day, "")
    if assigned and assigned != room5 and assigned not in (forbidden_ma or []):
        return assigned

    exclude = {room5, *(forbidden_ma or [])}
    for name in ordered_roster(surgeon_5, surgeon_7, surgeon_ma, forbidden_ma):
        if name and name not in exclude:
            return name
    return "Не назначен"


# Глобальные переменные, используемые в plan_core
SURGEON_5, SURGEON_7, SURGEON_MA, FORBIDDEN_MA = load_surgeons()
