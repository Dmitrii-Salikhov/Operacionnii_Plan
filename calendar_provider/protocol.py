"""Контракт бэкенда календаря — Google сегодня, другой провайдер завтра."""

from datetime import date
from typing import List, Protocol, runtime_checkable

from calendar_provider.types import CalendarEvent


@runtime_checkable
class CalendarBackend(Protocol):
    """Источник событий за неделю. Результат — список CalendarEvent."""

    name: str
    display_name: str

    def is_configured(self) -> bool:
        """True, если можно запрашивать события (есть ключи/настройки)."""
        ...

    def setup_help(self) -> str:
        """Текст подсказки для пользователя при отсутствии настройки."""
        ...

    def fetch_week_events(self, monday_date: date) -> List[CalendarEvent]:
        """События с понедельника monday_date по воскресенье (МСК)."""
        ...

    def reauthorize(self) -> None:
        """Повторная авторизация (если провайдер её использует)."""
        ...
