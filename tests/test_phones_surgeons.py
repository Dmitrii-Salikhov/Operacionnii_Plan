import config_surgeons
from phone_extractor import extract_phones_from_events


def test_phone_extractor_normalizes_and_skips_service_events():
    events = [
        {"Название события": "Иванов 7 л Адено 89064014401", "Описание": ""},
        {"Название события": "Закрыто для наркоза", "Описание": "79001234567"},
        {"Название события": "Петров 30 Септо 79001234567", "Описание": ""},
    ]
    assert extract_phones_from_events(events) == [
        ("79064014401", "Иванов"),
        ("79001234567", "Петров"),
    ]


def test_phone_extractor_uses_description_and_first_phone():
    result = extract_phones_from_events(
        [{"Название события": "Сидоров 89261234567", "Описание": "доп. 89064014401"}]
    )
    assert result == [("79261234567", "Сидоров")]


def test_phone_extractor_ignores_events_without_a_phone():
    assert extract_phones_from_events([{"Название события": "Иванов", "Описание": ""}]) == []


def test_phone_extractor_skips_empty_text_and_uses_fallback_surnames():
    events = [
        {"Название события": "", "Описание": ""},
        {"Название события": "123, 89064014401", "Описание": ""},
        {"Название события": "   79001234567", "Описание": ""},
    ]
    assert extract_phones_from_events(events) == [("79064014401", "123")]


def test_surgeon_config_saves_and_loads_temp_file(tmp_path, monkeypatch):
    path = tmp_path / "surgeons.json"
    monkeypatch.setattr(config_surgeons, "SURGEON_CONFIG_FILE", str(path))
    config_surgeons.save_surgeons(
        {0: "Новый Хирург"},
        "Другой Хирург",
        {0: "М/А Хирург"},
        ["Запрещен"],
    )
    assert config_surgeons.load_surgeons() == (
        {0: "Новый Хирург"},
        "Другой Хирург",
        {0: "М/А Хирург"},
        ["Запрещен"],
    )


def test_surgeon_config_missing_file_creates_defaults(tmp_path, monkeypatch):
    path = tmp_path / "missing.json"
    monkeypatch.setattr(config_surgeons, "SURGEON_CONFIG_FILE", str(path))
    surgeon_5, surgeon_7, surgeon_ma, forbidden = config_surgeons.load_surgeons()
    assert surgeon_5 == config_surgeons.DEFAULT_SURGEON_5
    assert surgeon_7 == config_surgeons.DEFAULT_SURGEON_7
    assert surgeon_ma == config_surgeons.DEFAULT_SURGEON_MA
    assert forbidden == config_surgeons.DEFAULT_FORBIDDEN_MA
    assert path.exists()
