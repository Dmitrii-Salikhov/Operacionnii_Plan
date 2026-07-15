from patient_parser import PatientParser
from plan_core import OperationPlanGenerator


def test_duplicate_surnames_receive_initials():
    parser = PatientParser()
    generator = OperationPlanGenerator(
        events_data=[
            {"Название события": "Иванов Иван 30 септо", "Дата начала (МСК)": "29.06.2026", "Время начала (МСК)": "10:00"},
            {"Название события": "Иванов Петр 31 септо", "Дата начала (МСК)": "29.06.2026", "Время начала (МСК)": "11:00"},
        ]
    )
    generator.parse_all_events()
    generator.distribute_patients()
    assert generator.surname_counts["Иванов"] == 2
    assert parser.build_display_name("Иванов Иван", generator.surname_counts) == "Иванов И."
    assert parser.build_display_name("Иванов Петр", generator.surname_counts) == "Иванов П."


def test_unique_surname_is_shown_without_initials():
    parser = PatientParser()
    generator = OperationPlanGenerator(
        events_data=[
            {"Название события": "Петров Петр 31 септо", "Дата начала (МСК)": "29.06.2026", "Время начала (МСК)": "10:00"},
        ]
    )
    generator.parse_all_events()
    generator.distribute_patients()
    assert generator.surname_counts["Петров"] == 1
    assert parser.build_display_name("Петров Петр", generator.surname_counts) == "Петров"
