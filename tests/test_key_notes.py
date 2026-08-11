"""Примечания, привязанные к ключу словаря."""

from patient_parser import PatientParser
from plan_core import OperationPlanGenerator


MONDAY = "29.06.2026"


def test_save_and_load_key_note(tmp_path):
    path = tmp_path / "custom.json"
    p = PatientParser(diagnosis_map={"септо": ("Септо", "Септопластика")}, custom_diag_file=str(path))
    p.save_custom_diagnosis("Доронина Н.С.", "J34", "Септопластика", note="Н.С.")
    assert p.key_notes["Доронина Н.С."] == "Н.С."
    assert "Н.С." in path.read_text(encoding="utf-8")
    assert '"Н.С."' in path.read_text(encoding="utf-8")

    p2 = PatientParser(diagnosis_map={}, custom_diag_file=str(path))
    assert p2.diagnosis_map["Доронина Н.С."] == ("J34", "Септопластика")
    assert p2.key_notes["Доронина Н.С."] == "Н.С."


def test_extract_bound_notes_removes_key_and_returns_note(tmp_path):
    path = tmp_path / "custom.json"
    p = PatientParser(diagnosis_map={}, custom_diag_file=str(path))
    p.save_custom_diagnosis("Доронина Н.С.", "J34", "Септопластика", note="Н.С.")
    cleaned, notes = p.extract_bound_notes("Иванов 30 септо Доронина Н.С.")
    assert "Доронина" not in cleaned
    assert "Иванов" in cleaned and "септо" in cleaned.lower()
    assert notes == "Н.С."


def test_bound_note_lands_on_admission_notes(tmp_path):
    path = tmp_path / "custom.json"
    # глобальный parser использует файл рядом с проектом — тестируем через локальный
    # экземпляр + подмена в plan через monkeypatch не нужна: вызовем extract напрямую
    from patient_parser import patient_parser

    old_file = patient_parser.custom_diag_file
    old_map = dict(patient_parser.diagnosis_map)
    old_notes = dict(patient_parser.key_notes)
    patient_parser.custom_diag_file = str(path)
    patient_parser.save_custom_diagnosis(
        "Доронина Н.С.", "J34.2 Искривление перегородки носа", "Септопластика", note="Н.С."
    )
    try:
        gen = OperationPlanGenerator(
            events_data=[
                {
                    "Название события": "Петров 30 септо Доронина Н.С.",
                    "Дата начала (МСК)": MONDAY,
                    "Время начала (МСК)": "10:00",
                }
            ]
        )
        gen.parse_all_events()
        gen.distribute_patients()
        patients = gen.daily_blocks[0]["5"]
        assert len(patients) == 1
        assert "Н.С." in (patients[0].get("notes") or "")
    finally:
        patient_parser.custom_diag_file = old_file
        patient_parser.diagnosis_map = old_map
        patient_parser.key_notes = old_notes
        patient_parser.sort_keys()
