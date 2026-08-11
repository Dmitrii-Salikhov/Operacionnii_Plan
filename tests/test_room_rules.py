"""Тесты room_rules и pick_ma_surgeon."""

from config_surgeons import pick_ma_surgeon
from room_rules import (
    classify_calendar_title,
    is_generalochka,
    is_narcosis_closed,
    is_service_event,
    is_tonsillectomy,
    extract_service_notes,
    load_service_note_aliases,
    save_service_note_alias,
    reload_room_rules,
)


def test_tonsil_keywords_and_short_token():
    assert is_tonsillectomy("Хронический тонзиллит, тонзилэктомия")
    assert is_tonsillectomy("т/э")
    assert is_tonsillectomy(" тэ ")
    assert not is_tonsillectomy("септопластика")


def test_narcosis_and_generalochka_classification():
    assert is_narcosis_closed("Закрыто для наркоза")
    assert is_narcosis_closed("Зарыто для наркоза")
    assert is_generalochka("Генералочка в операционной")
    assert classify_calendar_title("Закрыто для наркоза") == "narcosis_closed"
    assert classify_calendar_title("Генералочка") == "generalochka"
    assert classify_calendar_title("Каникулы") == "holiday"
    assert classify_calendar_title("для сотрудников") == "service"
    assert classify_calendar_title("Иванов 7 л Адено") is None
    assert is_service_event("Закрыто  для  наркоза")
    assert classify_calendar_title("ДА") == "service_note"
    assert classify_calendar_title("перенос") == "service_note"


def test_pick_ma_surgeon_uses_roster_not_hardcoded():
    surg5 = {0: "А А.А.", 1: "Б Б.Б.", 2: "В В.В.", 3: "Г Г.Г.", 4: "Д Д.Д."}
    surg_ma = {0: "А А.А.", 1: "Б Б.Б.", 2: "В В.В.", 3: "Г Г.Г.", 4: "Д Д.Д."}
    # День 0: М/А совпал с №5 → берём следующего из ростера (Б)
    assert pick_ma_surgeon(0, surg5, "Е Е.Е.", surg_ma, []) == "Б Б.Б."
    # Явный М/А без конфликта
    surg_ma[0] = "В В.В."
    assert pick_ma_surgeon(0, surg5, "Е Е.Е.", surg_ma, []) == "В В.В."
    # Все заняты forbidden / conflict → Не назначен
    assert pick_ma_surgeon(
        0,
        {0: "А А.А."},
        "А А.А.",
        {0: "А А.А."},
        ["А А.А."],
    ) == "Не назначен"


def test_reload_room_rules_from_defaults(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        '{"tonsil_keywords": ["супертонзил"], "generalochka_keywords": ["генка"]}',
        encoding="utf-8",
    )
    reload_room_rules(str(path))
    assert is_tonsillectomy("супертонзил сегодня")
    assert is_generalochka("генка")
    # Вернуть прод-правила
    reload_room_rules()


def test_service_note_aliases_can_override_j_token(tmp_path):
    # Алиас-словарь кладём в временный файл, чтобы не трогать реальные данные.
    alias_path = tmp_path / "aliases.json"
    alias_path.write_text("{}", encoding="utf-8")

    # Загружаем в кеш и проверяем базовое поведение.
    load_service_note_aliases(str(alias_path))
    cleaned, notes = extract_service_notes("Иванов (дж) 123")
    assert notes.strip() == "ДЖ"

    # Переопределяем: что именно должен выдавать токен «дж».
    save_service_note_alias("дж", "Джабраил", path=str(alias_path))
    load_service_note_aliases(str(alias_path))

    cleaned2, notes2 = extract_service_notes("Иванов (дж) 123")
    assert "Джабраил" in notes2
    assert "ДЖ" not in notes2

    # Откатить алиасы, чтобы другие тесты видели "дефолт".
    alias_path.write_text("{}", encoding="utf-8")
    load_service_note_aliases(str(alias_path))
