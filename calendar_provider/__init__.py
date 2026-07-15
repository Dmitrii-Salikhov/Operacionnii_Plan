"""Публичный фасад: загрузка недели и авторизация без привязки к Google."""

from datetime import date
from typing import List

from calendar_provider.factory import get_backend
from calendar_provider.protocol import CalendarBackend
from calendar_provider.types import CalendarEvent


def active_backend() -> CalendarBackend:
    """Текущий бэкенд из calendars.json (по умолчанию Google)."""
    return get_backend()


def calendar_display_name() -> str:
    return active_backend().display_name


def is_calendar_configured() -> bool:
    return active_backend().is_configured()


def calendar_setup_help() -> str:
    return active_backend().setup_help()


def fetch_week_events(monday_date: date) -> List[CalendarEvent]:
    """События за неделю с monday_date (нормализованный список для plan_core)."""
    return active_backend().fetch_week_events(monday_date)


def reauthorize() -> None:
    """Повторная авторизация текущего провайдера."""
    active_backend().reauthorize()
