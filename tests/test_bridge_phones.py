"""Тесты выгрузки телефонов через bridge (формат с 7 / без 7)."""

import pandas as pd
import pytest

from bridge import handlers


@pytest.fixture(autouse=True)
def _clear_bridge_session():
    handlers._SESSION.update(
        {"events": None, "filepath": None, "gen": None, "week_start": None}
    )
    yield
    handlers._SESSION.update(
        {"events": None, "filepath": None, "gen": None, "week_start": None}
    )


def _load_week_events():
    handlers._SESSION["events"] = [
        {"Название события": "Иванов 7 л Адено 79573332211", "Описание": ""},
        {"Название события": "Петров 30 Септо 89064014401", "Описание": ""},
        {"Название события": "Закрыто для наркоза", "Описание": "79001234567"},
    ]


def test_phones_extract_requires_calendar_week():
    with pytest.raises(RuntimeError, match="календаря"):
        handlers.dispatch("phones.extract", {})


def test_phones_extract_default_keeps_leading_7():
    _load_week_events()
    res = handlers.dispatch("phones.extract", {})
    assert res["format"] == "with_7"
    assert res["count"] == 2
    phones = [r["phone"] for r in res["rows"]]
    assert phones == ["79573332211", "79064014401"]


def test_phones_extract_without_7():
    _load_week_events()
    res = handlers.dispatch("phones.extract", {"format": "without_7"})
    assert res["format"] == "without_7"
    assert res["count"] == 2
    phones = [r["phone"] for r in res["rows"]]
    assert phones == ["9573332211", "9064014401"]


def test_phones_extract_strip_leading_7_flag():
    _load_week_events()
    res = handlers.dispatch("phones.extract", {"strip_leading_7": True})
    assert res["format"] == "without_7"
    assert [r["phone"] for r in res["rows"]] == ["9573332211", "9064014401"]


def test_phones_extract_aliases_no_7_and_10():
    _load_week_events()
    for fmt in ("no_7", "10", "local"):
        res = handlers.dispatch("phones.extract", {"format": fmt})
        assert res["format"] == "without_7"
        assert res["rows"][0]["phone"] == "9573332211"


def test_phones_extract_writes_excel(tmp_path):
    _load_week_events()
    out = tmp_path / "phones.xlsx"
    res = handlers.dispatch(
        "phones.extract",
        {"output_path": str(out), "format": "without_7"},
    )
    assert res["output_path"] == str(out)
    assert out.exists()
    df = pd.read_excel(out, sheet_name="Телефоны")
    assert list(df.columns) == ["Phone", "Name"]
    assert list(df["Phone"].astype(str)) == ["9573332211", "9064014401"]
    assert list(df["Name"].astype(str)) == ["Иванов", "Петров"]


def test_phones_extract_preserves_names_and_with_7_after_without():
    _load_week_events()
    without = handlers.dispatch("phones.extract", {"format": "without_7"})
    with7 = handlers.dispatch("phones.extract", {"format": "with_7"})
    assert [r["name"] for r in without["rows"]] == ["Иванов", "Петров"]
    assert [r["name"] for r in with7["rows"]] == ["Иванов", "Петров"]
    assert with7["rows"][0]["phone"] == "7" + without["rows"][0]["phone"]
