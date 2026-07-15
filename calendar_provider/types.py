"""Нормализованная форма события календаря (общая для всех провайдеров)."""

from typing import TypedDict

# Ключи с пробелами — синтаксис TypedDict через dict (совместимо с plan_core / Excel).
CalendarEvent = TypedDict(
    "CalendarEvent",
    {
        "Календарь": str,
        "Название события": str,
        "Описание": str,
        "Дата начала (МСК)": str,
        "Время начала (МСК)": str,
        "Дата окончания (МСК)": str,
        "Время окончания (МСК)": str,
    },
    total=False,
)
