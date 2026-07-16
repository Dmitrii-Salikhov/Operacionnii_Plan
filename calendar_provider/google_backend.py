"""Адаптер Google Calendar API v3."""

import logging
import os
import pickle
from datetime import date, datetime, timedelta, timezone
from typing import List

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from calendar_provider.config import ensure_calendars_config
from calendar_provider.types import CalendarEvent
from constants import CALENDARS_EXAMPLE_FILE, CALENDARS_FILE, CREDENTIALS_FILE

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = "token.pickle"
logger = logging.getLogger("plan_generator")


def get_google_calendar_service():
    """Возвращает сервис Google Calendar, автоматически обновляя токен."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except (RefreshError, GoogleAuthError, OSError) as e:
                logger.warning("Не удалось обновить Google-токен: %s", e)
                os.remove(TOKEN_FILE)
                return reauthorize_google()
        else:
            return reauthorize_google()
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("calendar", "v3", credentials=creds)


def reauthorize_google():
    """Принудительно запускает OAuth и сохраняет новый токен."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Нет файла {CREDENTIALS_FILE}. Скопируйте credentials.example.json "
            f"в {CREDENTIALS_FILE} и заполните данными OAuth-клиента из Google Cloud."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "wb") as token:
        pickle.dump(creds, token)
    return build("calendar", "v3", credentials=creds)


def fetch_google_calendar_events(monday_date: date) -> List[CalendarEvent]:
    """Загружает события за неделю с понедельника monday_date (МСК)."""
    calendar_ids = ensure_calendars_config()
    if not calendar_ids:
        raise ValueError(
            f"Не заданы календари в {CALENDARS_FILE}.\n\n"
            f"Откройте файл рядом с программой (образец: {CALENDARS_EXAMPLE_FILE}) "
            "и укажите реальные email/ID календарей Google в calendar_ids.\n"
            "Шаблонные адреса вроде your-first-calendar@gmail.com не работают."
        )

    service = get_google_calendar_service()
    msk = timezone(timedelta(hours=3))
    monday_start = datetime.combine(monday_date, datetime.min.time(), tzinfo=msk)
    sunday_end = datetime.combine(
        monday_date + timedelta(days=6), datetime.max.time(), tzinfo=msk
    )
    time_min = monday_start.isoformat()
    time_max = sunday_end.isoformat()

    all_events: List[CalendarEvent] = []
    for cal_id in calendar_ids:
        try:
            events_result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status == 404:
                raise ValueError(
                    f"Календарь не найден: {cal_id}\n\n"
                    f"Проверьте {CALENDARS_FILE} рядом с программой — "
                    "там должны быть реальные email/ID, к которым есть доступ у аккаунта Google."
                ) from e
            raise
        for event in events_result.get("items", []):
            start_raw = event["start"].get("dateTime", event["start"].get("date"))
            end_raw = event["end"].get("dateTime", event["end"].get("date"))

            if "T" in start_raw:
                date_part, time_part_with_tz = start_raw.split("T")
                time_part = time_part_with_tz[:8]
            else:
                date_part = start_raw
                time_part = "00:00:00"

            if "T" in end_raw:
                end_time_part = end_raw.split("T")[1][:8]
            else:
                end_time_part = "00:00:00"

            if "date" in event["start"] and "dateTime" not in event["start"]:
                continue

            all_events.append(
                {
                    "Календарь": cal_id,
                    "Название события": event.get("summary", ""),
                    "Описание": event.get("description", ""),
                    "Дата начала (МСК)": date_part,
                    "Время начала (МСК)": time_part,
                    "Дата окончания (МСК)": end_raw.split("T")[0]
                    if "T" in end_raw
                    else end_raw,
                    "Время окончания (МСК)": end_time_part,
                }
            )
    return all_events


class GoogleCalendarBackend:
    """Бэкенд Google Calendar."""

    name = "google"
    display_name = "Google Календарь"

    def is_configured(self) -> bool:
        return os.path.exists(CREDENTIALS_FILE)

    def setup_help(self) -> str:
        return (
            f"Отсутствует файл {CREDENTIALS_FILE}, необходимый для доступа "
            f"к {self.display_name}.\n\n"
            "1. Скопируйте credentials.example.json → credentials.json\n"
            "2. Создайте OAuth client (Desktop) в Google Cloud Console\n"
            "   APIs & Services → Credentials → Create OAuth client ID\n"
            "3. Вставьте client_id и client_secret в credentials.json\n\n"
            "Если секрет когда-либо попадал в интернет — сначала отзовите "
            "старый client secret в Google Cloud и создайте новый.\n\n"
            f"Календари задаются в {CALENDARS_FILE} "
            f"(образец: {CALENDARS_EXAMPLE_FILE}).\n"
            'Поле "provider": "google" — смена провайдера позже.\n\n'
            "Пока можно загрузить данные из Excel-файла."
        )

    def fetch_week_events(self, monday_date: date) -> List[CalendarEvent]:
        return fetch_google_calendar_events(monday_date)

    def reauthorize(self) -> None:
        reauthorize_google()
