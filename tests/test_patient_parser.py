from collections import Counter
from datetime import datetime
import json

import pytest

from patient_parser import PatientParser, load_diagnosis_map_from_json


def parser():
    return PatientParser()


def test_extracts_ages_and_cleans_text():
    subject = parser()
    cases = [
        ("Иванов 7 л Адено", 7, "л"),
        ("Петров 5 адено", 5, "л"),
        ("Козлов 45 г.", 45, "г"),
    ]
    for text, expected_age, expected_unit in cases:
        age, unit, clean = subject.extract_age_and_clean(text)
        assert (age, unit) == (expected_age, expected_unit)
        assert "Иванов" in clean or "Петров" in clean or "Козлов" in clean


def test_extracts_birth_year_and_date_of_birth():
    subject = parser()
    age, unit, clean = subject.extract_age_and_clean("Сидоров 1980 г.р. Септо")
    assert (age, unit) == (datetime.now().year - 1980, "л")
    assert "Септо" in clean
    age, unit, clean = subject.extract_age_and_clean("Алексеев 15.03.2010")
    assert (age, unit) == (datetime.now().year - 2010, "л")
    assert "15.03.2010" not in clean


def test_missing_and_invalid_age_are_unchanged():
    subject = parser()
    assert subject.extract_age_and_clean("")[0:2] == (None, None)
    assert subject.extract_age_and_clean("Иванов Тонзилэктомия")[0:2] == (None, None)


def test_normalizes_names_and_removes_birth_markers():
    subject = parser()
    assert subject.normalize_name("иванов иван иванович") == "Иванов Иван Иванович"
    assert subject.normalize_name("Петров А.В.") == "Петров А.В."
    assert subject.normalize_name("Сидоров г.р. 1980") == "Сидоров"
    assert subject.normalize_name("") == ""


def test_diagnosis_classification_and_combinations():
    subject = parser()
    diag, operation = subject.get_diagnosis_and_operation("Адено")
    assert "Аденоиды" in diag and "Аденотомия" in operation
    diag, operation = subject.get_diagnosis_and_operation("септо вазо")
    assert "Искривление перегородки" in diag and "пластика раковин" in operation.lower()
    diag, operation = subject.get_diagnosis_and_operation("А+ВР")
    assert "Аденотомия" in operation and "пластика раковин" in operation.lower()
    diag, operation = subject.get_diagnosis_and_operation("септо полип")
    assert "Полип" in diag and "удаление полипа" in operation.lower()
    diag, operation = subject.get_diagnosis_and_operation("А+М")
    assert "миринготомия" in operation.lower()


def test_unknown_diagnosis_is_returned_as_raw_text():
    diag, operation = parser().get_diagnosis_and_operation("Фантастический диагноз")
    assert (diag, operation) == ("Фантастический диагноз", "Операция не указана")


def test_complex_diagnosis_combinations_keep_all_operations():
    subject = parser()
    cases = [
        ("септо вазо синусит", "гайморотомия"),
        ("септо вазо увуло", "увулопластика"),
        ("септо вазо адено", "аденотомия"),
        ("септо вазо киста", "гайморотомия"),
        ("септо тонзилэктомия увулопластика", "тонзилэктомия"),
        ("септо полисинусотомия", "полисинусотомия"),
        ("септо увулопластика", "увулопластика"),
        ("септо синехии", "синехотомия"),
        ("септо папилома миндалины", "удаление образования"),
        ("септо киста", "гайморотомия"),
        ("септо гайморо", "гайморотомия"),
        ("гайморо вазо", "пластика раковин"),
        ("вазо синехии", "синехотомия"),
        ("адено миринго", "миринготомия"),
        ("адено вазо", "пластика раковин"),
    ]
    for raw, expected_operation in cases:
        _, operation = subject.get_diagnosis_and_operation(raw)
        assert expected_operation in operation.lower()


def test_full_event_parsing_flags_and_phone_cleanup():
    subject = parser()
    patient = subject.parse_patient_from_event("Иванов 7 л Адено 89064014401", "")
    assert patient["name"] == "Иванов"
    assert patient["age"] == 7
    assert patient["phones"] == []
    assert "890640" not in patient["diagnosis_raw"]

    patient = subject.parse_patient_from_event("Петров 45 М/А Септо", "")
    assert patient["is_ma"] is True
    patient = subject.parse_patient_from_event("Сидоров остеотомия септо", "")
    assert patient["has_osteotomy"] is True
    assert subject.parse_patient_from_event("", "") is None
    short = subject.parse_patient_from_event("А. 5 л Адено", "")
    assert short is not None
    assert short["needs_name_review"] is True
    assert short["name"].replace(".", "") == "А"


def test_unknown_and_service_titles_are_parser_inputs():
    subject = parser()
    assert subject.parse_patient_from_event("Шолохов вазо", "")["is_unknown_diag"] is False
    assert subject.parse_patient_from_event("НеизвестныйДиагноз 30", "")["is_unknown_diag"] is True
    assert subject.parse_patient_from_event("Закрыто для наркоза", "")["is_unknown_diag"] is True


def test_sanitize_and_clean_phone_numbers():
    subject = parser()
    assert subject.sanitize_text("Иванов\u00a07\xa0лет") == "Иванов 7 лет"
    assert subject.sanitize_text("  много   пробелов ") == "много пробелов"
    assert "89064014401" not in subject.clean_phone_numbers("Петров 89064014401")
    assert "906" not in subject.clean_phone_numbers("Сидоров +7(906)401-44-01")


def test_surname_initials_display_and_age_defaults():
    subject = parser()
    assert subject.get_surname_and_initials("Иванов Иван Иванович") == ("Иванов", "И.И.")
    assert subject.get_surname_and_initials("Петров А.В.") == ("Петров", "А.В.")
    assert subject.build_display_name("Иванов Иван", Counter(["Иванов"])) == "Иванов"
    assert subject.build_display_name("Петров И.И.", Counter(["Петров", "Петров"])) == "Петров И.И."
    assert subject.resolve_age_defaults("Аденоиды", None) == (5, "л")
    assert subject.resolve_age_defaults("Септопластика", None) == (44, "г")


def test_custom_diagnoses_load_save_and_full_save(tmp_path):
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"custom": ["Диагноз", "Операция"]}), encoding="utf-8")
    subject = PatientParser(diagnosis_map={"base": ("База", "Базовая")}, custom_diag_file=str(path))
    assert subject.get_diagnosis_and_operation("custom") == ("Диагноз", "Операция")

    subject.save_custom_diagnosis("new", "Новый диагноз", "Новая операция")
    assert json.loads(path.read_text(encoding="utf-8"))["new"] == ["Новый диагноз", "Новая операция"]
    subject.save_custom_diagnoses_full()
    assert "base" in json.loads(path.read_text(encoding="utf-8"))


def test_invalid_birth_date_falls_back_without_raising():
    subject = parser()
    age, unit, clean = subject.extract_age_and_clean("Иванов 31.02.2010 септо")
    assert (age, unit) == (2010, "л")
    assert "септо" in clean


def test_short_diagnosis_keys_require_word_boundaries_and_bracketed_diagnoses():
    subject = PatientParser(diagnosis_map={"ат": ("Ат", "Операция"), "септо": ("Септо", "Операция")})
    assert subject.parse_patient_from_event("Иванов патология", "")["is_unknown_diag"] is True
    patient = subject.parse_patient_from_event("Иванов (септо)", "")
    assert patient["name"] == "Иванов"
    assert patient["diagnosis_raw"] == "септо"


def test_parser_empty_unknown_and_logger_callbacks():
    messages = []
    subject = parser()
    assert subject.parse_patient_from_event("Иванов", "", logger=lambda message: messages.append(message))["diagnosis_raw"] == ""
    assert subject.parse_patient_from_event("Иванов 7 л", "") is not None
    assert subject.parse_patient_from_event("Иванов 7 л", "", logger=lambda message: messages.append(message))
    assert any("[ИСХОДНАЯ]" in message for message in messages)
    assert any("[ФИНАЛ]" in message for message in messages)


def test_additional_diagnosis_fallbacks_and_map_paths():
    subject = parser()
    cases = [
        ("хрон синусит вазо", "гайморотомия"),
        ("полисинусотомия", "полисинусотомия"),
        ("увулопалато", "увулопластика"),
        ("атерома", "удаление образования"),
        ("", "операция не указана"),
    ]
    for raw, expected_operation in cases:
        _, operation = subject.get_diagnosis_and_operation(raw)
        assert expected_operation in operation.lower()


def test_parser_covers_age_name_bracket_and_short_key_paths(tmp_path):
    subject = PatientParser(diagnosis_map={"ат": ("Ат", "Операция"), "diag": ("Диагноз", "Операция")},
                            custom_diag_file=str(tmp_path / "custom.json"))
    assert subject.extract_age_and_clean("Иванов 1980 г")[0:2] == (datetime.now().year - 1980, "л")
    assert subject.normalize_name("Иванов г.") == "Иванов"
    assert subject.get_surname_and_initials("") == ("", "")

    logs = []
    patient = subject.parse_patient_from_event("Иванов ат (diag)", "", logger=logs.append)
    assert patient["diagnosis_raw"].split() == ["ат", "diag"]
    assert any("[ФИНАЛ]" in message for message in logs)
    unknown = subject.parse_patient_from_event("Иванов неизвестно", "")
    assert unknown["is_unknown_diag"] is True


def test_short_real_surname_goes_to_name_review_not_ignored(tmp_path):
    """Фамилия из 1–2 букв (напр. «Е») — на уточнение, не игнор."""
    subject = PatientParser(
        diagnosis_map={"ат": ("Ат", "Аденотомия")},
        custom_diag_file=str(tmp_path / "custom.json"),
    )
    logs = []
    patient = subject.parse_patient_from_event(
        "Е 5 л АТ 89781543455", "", logger=logs.append
    )
    assert patient is not None
    assert patient["name"].replace(".", "") == "Е"
    assert patient["age"] == 5
    assert patient["diagnosis_raw"].lower() == "ат"
    assert patient["needs_name_review"] is True
    assert patient["is_unknown_diag"] is False
    assert any("НА УТОЧНЕНИЕ" in m for m in logs)
    assert not any("ИГНОРИРОВАНО" in m and "короткое" in m.lower() for m in logs)


def test_diagnosis_fallbacks_work_without_a_configured_map(tmp_path):
    subject = PatientParser(diagnosis_map={}, custom_diag_file=str(tmp_path / "custom.json"))
    cases = [
        ("адено", "аденотомия"),
        ("тонзил", "тонзилэктомия"),
        ("септо", "септопластика"),
        ("вазо", "пластика раковин"),
        ("гайморо", "гайморотомия"),
        ("атерома", "удаление образования"),
        ("", "операция не указана"),
    ]
    for raw, expected_operation in cases:
        _, operation = subject.get_diagnosis_and_operation(raw)
        assert expected_operation in operation.lower()


def test_diagnosis_json_validation_rejects_malformed_values(tmp_path):
    path = tmp_path / "diagnoses.json"
    path.write_text(json.dumps({"ok": ["Диагноз", "Операция"]}), encoding="utf-8")
    assert load_diagnosis_map_from_json(path) == {"ok": ("Диагноз", "Операция")}
    path.write_text(json.dumps({"bad": ["only one"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Неверный формат"):
        load_diagnosis_map_from_json(path)
