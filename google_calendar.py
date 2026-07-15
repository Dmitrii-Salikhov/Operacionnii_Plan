"""
Обратная совместимость для старых импортов.

Новый код: from calendar_provider import fetch_week_events, reauthorize
Провайдер задаётся в calendars.json: "provider": "google"
"""

from constants import CREDENTIALS_FILE  # noqa: F401
from calendar_provider.config import (  # noqa: F401
    CALENDARS_EXAMPLE_FILE,
    CALENDARS_FILE,
    DEFAULT_CALENDAR_IDS,
    ensure_calendars_config,
    load_calendar_ids,
    logger,
)
from calendar_provider.google_backend import (  # noqa: F401
    SCOPES,
    fetch_google_calendar_events,
    get_google_calendar_service,
    reauthorize_google,
)
