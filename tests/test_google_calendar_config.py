"""Тесты Google Calendar backend."""

import json

import calendar_provider.config as cal_config
import calendar_provider.google_backend as google_cal
from google.auth.exceptions import RefreshError


def test_refresh_failure_reauthorizes_without_network(tmp_path, monkeypatch):
    class ExpiredCredentials:
        valid = False
        expired = True
        refresh_token = "refresh"

        def refresh(self, _):
            raise RefreshError("expired")

    credentials = ExpiredCredentials()
    removed = []
    monkeypatch.chdir(tmp_path)
    (tmp_path / "token.pickle").write_bytes(b"token")
    monkeypatch.setattr(google_cal.os.path, "exists", lambda path: path == google_cal.TOKEN_FILE)
    monkeypatch.setattr(google_cal.pickle, "load", lambda _: credentials)
    monkeypatch.setattr(google_cal.os, "remove", lambda path: removed.append(path))
    sentinel = object()
    monkeypatch.setattr(google_cal, "reauthorize_google", lambda: sentinel)
    assert google_cal.get_google_calendar_service() is sentinel
    assert removed == [google_cal.TOKEN_FILE]


def test_valid_and_refreshed_credentials_build_service(tmp_path, monkeypatch):
    class Credentials:
        valid = True

    valid = Credentials()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "token.pickle").write_bytes(b"token")
    monkeypatch.setattr(google_cal.os.path, "exists", lambda path: path == google_cal.TOKEN_FILE)
    monkeypatch.setattr(google_cal.pickle, "load", lambda _: valid)
    sentinel = object()
    monkeypatch.setattr(google_cal, "build", lambda *args, **kwargs: sentinel)
    assert google_cal.get_google_calendar_service() is sentinel

    class RefreshableCredentials:
        valid = False
        expired = True
        refresh_token = "refresh"

        def refresh(self, _):
            self.valid = True

    refreshed = RefreshableCredentials()
    monkeypatch.setattr(google_cal.pickle, "load", lambda _: refreshed)
    dumped = []
    monkeypatch.setattr(google_cal.pickle, "dump", lambda credentials, _: dumped.append(credentials))
    assert google_cal.get_google_calendar_service() is sentinel
    assert dumped == [refreshed]


def test_reauthorize_requires_credentials_and_builds_service(tmp_path, monkeypatch):
    credentials_path = tmp_path / "credentials.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(google_cal, "CREDENTIALS_FILE", str(credentials_path))
    try:
        google_cal.reauthorize_google()
    except FileNotFoundError as error:
        assert "Нет файла" in str(error)
    else:
        raise AssertionError("Expected credentials validation to fail")

    credentials_path.write_text("{}", encoding="utf-8")

    class Flow:
        def run_local_server(self, port):
            assert port == 0
            return "credentials"

    monkeypatch.setattr(
        google_cal.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: Flow(),
    )
    monkeypatch.setattr(google_cal.pickle, "dump", lambda *_: None)
    sentinel = object()
    monkeypatch.setattr(google_cal, "build", lambda *args, **kwargs: sentinel)
    assert google_cal.reauthorize_google() is sentinel


def test_fetch_requires_a_calendar_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(tmp_path / "missing.json"))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "missing.example.json"))
    try:
        google_cal.fetch_google_calendar_events(__import__("datetime").date(2026, 6, 29))
    except ValueError as error:
        assert "Не заданы календари" in str(error)
    else:
        raise AssertionError("Expected missing calendars to fail")


def test_fetch_google_events_uses_configured_calendars_without_oauth(tmp_path, monkeypatch):
    calendars = tmp_path / "calendars.json"
    calendars.write_text(json.dumps(["calendar-a"]), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(calendars))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "missing.json"))

    class Request:
        def list(self, **kwargs):
            assert kwargs["calendarId"] == "calendar-a"
            return self

        def execute(self):
            return {
                "items": [
                    {
                        "summary": "Иванов",
                        "description": "Описание",
                        "start": {"dateTime": "2026-06-29T10:00:00+03:00"},
                        "end": {"dateTime": "2026-06-29T11:00:00+03:00"},
                    },
                    {
                        "summary": "All-day",
                        "start": {"date": "2026-06-30"},
                        "end": {"date": "2026-06-30"},
                    },
                ]
            }

    class Service:
        def events(self):
            return Request()

    monkeypatch.setattr(google_cal, "get_google_calendar_service", lambda: Service())
    events = google_cal.fetch_google_calendar_events(__import__("datetime").date(2026, 6, 29))
    assert events == [
        {
            "Календарь": "calendar-a",
            "Название события": "Иванов",
            "Описание": "Описание",
            "Дата начала (МСК)": "2026-06-29",
            "Время начала (МСК)": "10:00:00",
            "Дата окончания (МСК)": "2026-06-29",
            "Время окончания (МСК)": "11:00:00",
        }
    ]
