"""Тесты списка календарей и сохранения."""

import json

from calendar_provider.config import load_calendar_ids, save_calendar_ids
from bridge import handlers


def test_save_and_load_calendar_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = save_calendar_ids(["a@gmail.com", "b@gmail.com", "your-first-calendar@x.com"])
    assert saved == ["a@gmail.com", "b@gmail.com"]
    data = json.loads((tmp_path / "calendars.json").read_text(encoding="utf-8"))
    assert data["provider"] == "google"
    assert data["calendar_ids"] == ["a@gmail.com", "b@gmail.com"]
    assert load_calendar_ids() == ["a@gmail.com", "b@gmail.com"]


def test_save_empty_calendar_ids_respected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "calendars.example.json").write_text(
        json.dumps({"provider": "google", "calendar_ids": ["example@gmail.com"]}),
        encoding="utf-8",
    )
    save_calendar_ids([])
    assert load_calendar_ids() == []


def test_bridge_calendar_set_and_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLAN_BASE_DIR", str(tmp_path))
    (tmp_path / "version.txt").write_text("1.1.0", encoding="utf-8")
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")

    res = handlers.dispatch(
        "calendar.set_ids",
        {"calendar_ids": ["one@x.com", "two@x.com"]},
    )
    assert res["calendar_ids"] == ["one@x.com", "two@x.com"]

    status = handlers.dispatch("calendar.status", {})
    assert status["calendar_ids"] == ["one@x.com", "two@x.com"]
    assert len(status["switch_steps"]) >= 4

    # unit-test count helper via fetch response shape without network
    events = [
        {"Календарь": "one@x.com", "Название события": "A"},
        {"Календарь": "one@x.com", "Название события": "B"},
        {"Календарь": "two@x.com", "Название события": "C"},
    ]
    counts = handlers._event_counts_by_calendar(events)
    assert counts == [
        {"calendar_id": "one@x.com", "count": 2},
        {"calendar_id": "two@x.com", "count": 1},
    ]
