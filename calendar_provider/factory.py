"""Фабрика бэкендов календаря."""

from typing import Optional

from calendar_provider.config import KNOWN_PROVIDERS, load_provider
from calendar_provider.google_backend import GoogleCalendarBackend
from calendar_provider.protocol import CalendarBackend


def get_backend(provider: Optional[str] = None) -> CalendarBackend:
    """
    Возвращает бэкенд по имени (из аргумента или calendars.json).

    Чтобы добавить другой календарь (не Google):
    1. Реализуйте класс с тем же интерфейсом, что GoogleCalendarBackend.
    2. Зарегистрируйте его здесь.
    3. Добавьте имя в KNOWN_PROVIDERS.
    4. В calendars.json укажите "provider": "<имя>".
    """
    name = (provider or load_provider()).strip().lower() or "google"
    if name == "google":
        return GoogleCalendarBackend()
    known = ", ".join(sorted(KNOWN_PROVIDERS))
    raise ValueError(
        f"Провайдер календаря «{name}» не реализован. "
        f"Сейчас доступно: {known}. "
        "Добавьте адаптер в calendar_provider и пропишите его в get_backend()."
    )
