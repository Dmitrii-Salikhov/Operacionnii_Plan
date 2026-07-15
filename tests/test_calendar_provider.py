"""Тесты конфига и фабрики провайдера календаря."""

import json

import calendar_provider.config as cal_config
from calendar_provider.factory import get_backend
from calendar_provider.google_backend import GoogleCalendarBackend


def test_load_calendar_ids_prefers_primary_file(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    example = tmp_path / "calendars.example.json"
    primary.write_text(json.dumps({"calendar_ids": [" first ", "", 123]}), encoding="utf-8")
    example.write_text(json.dumps(["fallback"]), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(example))
    assert cal_config.load_calendar_ids() == ["first", "123"]


def test_load_calendar_ids_uses_example_and_empty_default(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    example = tmp_path / "calendars.example.json"
    example.write_text(json.dumps(["example-id"]), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(example))
    assert cal_config.load_calendar_ids() == ["example-id"]
    example.unlink()
    assert cal_config.load_calendar_ids() == []


def test_ensure_calendars_config_copies_example(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    example = tmp_path / "calendars.example.json"
    example.write_text(json.dumps({"calendars": ["copied-id"]}), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(example))
    assert cal_config.ensure_calendars_config() == ["copied-id"]
    assert json.loads(primary.read_text(encoding="utf-8")) == {"calendars": ["copied-id"]}


def test_calendar_config_handles_invalid_json_and_copy_error(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    example = tmp_path / "calendars.example.json"
    primary.write_text("{invalid", encoding="utf-8")
    example.write_text(json.dumps({"calendar_ids": []}), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(example))
    monkeypatch.setattr(cal_config, "DEFAULT_CALENDAR_IDS", ["default"])
    warnings = []
    monkeypatch.setattr(cal_config.logger, "warning", lambda *args: warnings.append(args))
    assert cal_config.load_calendar_ids() == ["default"]
    assert "Не удалось прочитать" in warnings[0][0]

    primary.unlink()
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("denied")))
    assert cal_config.ensure_calendars_config() == ["default"]


def test_load_provider_defaults_to_google(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    primary.write_text(json.dumps({"calendar_ids": ["a"]}), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "x.json"))
    assert cal_config.load_provider() == "google"


def test_load_provider_reads_field(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    primary.write_text(
        json.dumps({"provider": "Google", "calendar_ids": ["a"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "x.json"))
    assert cal_config.load_provider() == "google"


def test_get_backend_google(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    primary.write_text(json.dumps({"provider": "google", "calendar_ids": ["a"]}), encoding="utf-8")
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "x.json"))
    backend = get_backend()
    assert isinstance(backend, GoogleCalendarBackend)
    assert backend.name == "google"


def test_get_backend_unknown_provider(tmp_path, monkeypatch):
    primary = tmp_path / "calendars.json"
    primary.write_text(
        json.dumps({"provider": "outlook", "calendar_ids": ["a"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cal_config, "CALENDARS_FILE", str(primary))
    monkeypatch.setattr(cal_config, "CALENDARS_EXAMPLE_FILE", str(tmp_path / "x.json"))
    try:
        get_backend()
    except ValueError as error:
        assert "outlook" in str(error)
        assert "не реализован" in str(error)
    else:
        raise AssertionError("Expected unknown provider to fail")
