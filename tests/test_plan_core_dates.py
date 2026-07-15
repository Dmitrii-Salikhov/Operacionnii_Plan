from datetime import datetime

import pandas as pd
import pytest

from plan_core import OperationPlanGenerator, is_service_event, parse_time_str


def event(title, date, time="10:00"):
    return {
        "Название события": title,
        "Дата начала (МСК)": date,
        "Время начала (МСК)": time,
    }


def test_parse_time_str_accepts_common_formats_and_default():
    assert str(parse_time_str("09:30")) == "09:30:00"
    assert str(parse_time_str("09:30:10")) == "09:30:10"
    assert str(parse_time_str("", default=parse_time_str("00:00"))) == "00:00:00"


def test_dates_parse_to_correct_weekdays_and_week_start():
    events = [
        event("Пациент 30 септо", "01.04.2026", ""),
        event("Пациент 10 адено", "2026-04-08T09:00:00", "09:00"),
        event("Пациент 10 адено", "  03.04.2026  "),
    ]
    generator = OperationPlanGenerator(events_data=events)
    generator.parse_all_events()
    assert len(generator.events_by_day[2]) == 2
    assert len(generator.events_by_day[4]) == 1
    assert generator.week_start.date() == datetime(2026, 3, 30).date()


def test_first_valid_event_determines_week_start():
    generator = OperationPlanGenerator(
        events_data=[event("Первый", "02.04.2026"), event("Второй", "30.03.2026")]
    )
    generator.parse_all_events()
    assert generator.week_start.date() == datetime(2026, 3, 30).date()


def test_empty_and_bad_dates_are_skipped_with_warning():
    warnings = []
    generator = OperationPlanGenerator(
        events_data=[
            event("Без даты", ""),
            event("", "01.04.2026"),
            event("Пациент 10 Адено", "не дата"),
        ],
        log_callback=lambda message, tag="info": warnings.append(message) if tag == "warning" else None,
    )
    generator.parse_all_events()
    assert sum(len(day) for day in generator.events_by_day.values()) == 0
    assert any("Некорректная дата" in warning for warning in warnings)


def test_service_event_detection_and_registration():
    assert is_service_event("Закрыто  для  наркоза")
    assert is_service_event("Зарыто для наркоза")
    assert is_service_event("Генералочка в операционной")
    assert is_service_event("Каникулы")
    assert not is_service_event("Иванов 7 л Адено")

    generator = OperationPlanGenerator(
        events_data=[event("закрыто для наркоза", "02.04.2026", "12:00"), event("Генералочка", "01.04.2026", "08:00")]
    )
    generator.parse_all_events()
    assert generator.events_by_day[3][0]["type"] == "narcosis_closed"
    assert generator.events_by_day[2][0]["type"] == "generalochka"
    assert 2 in generator.generalochka_days


def test_constructor_requires_data_and_loads_valid_excel_sheets(tmp_path):
    with pytest.raises(ValueError, match="Нет данных"):
        OperationPlanGenerator()

    path = tmp_path / "events.xlsx"
    valid = pd.DataFrame([event("Иванов 30 септо", "29.06.2026")])
    invalid = pd.DataFrame({"other": ["ignored"]})
    with pd.ExcelWriter(path) as writer:
        valid.to_excel(writer, sheet_name="valid", index=False)
        invalid.to_excel(writer, sheet_name="invalid", index=False)

    generator = OperationPlanGenerator(filepath=str(path))
    assert len(generator.df) == 1
    generator.parse_all_events()
    assert generator.events_by_day[0][0]["name"] == "Иванов"

    invalid_path = tmp_path / "invalid.xlsx"
    invalid.to_excel(invalid_path, index=False)
    with pytest.raises(ValueError, match="Ни один лист"):
        OperationPlanGenerator(filepath=str(invalid_path))


def test_holidays_and_other_service_events_are_skipped_with_logs():
    messages = []
    generator = OperationPlanGenerator(
        events_data=[
            event("Праздник", "29.06.2026"),
            event("Выходной", "29.06.2026"),
            event("Каникулы", "29.06.2026"),
            event("Для сотрудников", "29.06.2026"),
        ],
        log_callback=lambda message, tag="info": messages.append((message, tag)),
    )
    generator.parse_all_events()
    assert generator.events_by_day[0] == []
    assert any("Служебное событие" in message for message, _ in messages)
    assert is_service_event("для сотрудников")


def test_parse_time_str_raises_without_default():
    with pytest.raises(ValueError, match="Некорректное время"):
        parse_time_str("bad-time")
