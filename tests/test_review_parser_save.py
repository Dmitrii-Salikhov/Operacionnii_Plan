"""Сохранение уточнённых диагнозов в парсер через plan.export."""

import tempfile
from datetime import date
from pathlib import Path

from patient_parser import patient_parser
from plan_core import OperationPlanGenerator
from bridge import handlers


def _patient(**kwargs):
    base = {
        "name": "Неизвестный",
        "age": 30,
        "age_unit": "л",
        "diagnosis_raw": "",
        "diagnosis": "Диагноз не указан",
        "operation": "Операция не указана",
        "is_unknown_diag": True,
        "needs_name_review": False,
        "confidence": 0.0,
        "is_ma": False,
        "is_etn": False,
        "has_osteotomy": False,
        "phones": [],
        "full_text": "Неизвестный 30 xyzop",
        "time": "10:00",
    }
    base.update(kwargs)
    return base


def test_collect_reviews_exposes_source_text_and_editable_key():
    gen = OperationPlanGenerator(events_data=[])
    gen.daily_blocks[0]["5"] = [
        _patient(full_text="Неизвестный 30 xyzop", diagnosis_raw="")
    ]
    rows = handlers._collect_reviews(gen)
    assert rows[0]["source_text"] == "Неизвестный 30 xyzop"
    assert rows[0]["diagnosis_raw"] == ""


def test_plan_export_saves_edited_key_to_parser(tmp_path):
    custom = tmp_path / "custom_diagnoses.json"
    old = patient_parser.custom_diag_file
    patient_parser.custom_diag_file = str(custom)
    # убрать возможный ключ из прошлого прогона
    patient_parser.diagnosis_map.pop("xyzop", None)

    gen = OperationPlanGenerator(events_data=[])
    gen.week_start = date(2026, 6, 29)
    patient = _patient()
    gen.daily_blocks[0]["5"] = [patient]
    handlers._collect_reviews(gen)
    rid = patient["_bridge_id"]

    handlers._SESSION["gen"] = gen
    out = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    out.close()
    try:
        result = handlers.plan_export(
            {
                "output_path": out.name,
                "reviews": [
                    {
                        "id": rid,
                        "name": "Неизвестный",
                        "diagnosis_raw": "xyzop",
                        "diagnosis": "Хронический ринит",
                        "operation": "Конхотомия",
                        "note": "Н.С.",
                        "room": "5",
                        "remember": True,
                    }
                ],
            }
        )
        assert patient["diagnosis_raw"] == "xyzop"
        assert patient["diagnosis"] == "Хронический ринит"
        assert patient_parser.diagnosis_map["xyzop"] == (
            "Хронический ринит",
            "Конхотомия",
        )
        assert patient_parser.key_notes.get("xyzop") == "Н.С."
        assert custom.exists()
        assert any("В парсер: «xyzop»" in row["message"] for row in result["logs"])
        assert any("примечание «Н.С.»" in row["message"] for row in result["logs"])
    finally:
        handlers._SESSION["gen"] = None
        patient_parser.custom_diag_file = old
        patient_parser.diagnosis_map.pop("xyzop", None)
        patient_parser.key_notes.pop("xyzop", None)
        Path(out.name).unlink(missing_ok=True)


def test_plan_export_remember_without_key_warns(tmp_path):
    gen = OperationPlanGenerator(events_data=[])
    gen.week_start = date(2026, 6, 29)
    patient = _patient()
    gen.daily_blocks[0]["5"] = [patient]
    handlers._collect_reviews(gen)
    rid = patient["_bridge_id"]

    handlers._SESSION["gen"] = gen
    out = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    out.close()
    try:
        result = handlers.plan_export(
            {
                "output_path": out.name,
                "reviews": [
                    {
                        "id": rid,
                        "name": "Неизвестный",
                        "diagnosis_raw": "",
                        "diagnosis": "Хронический ринит",
                        "operation": "Конхотомия",
                        "remember": True,
                    }
                ],
            }
        )
        assert any("не сохранено в парсер" in row["message"] for row in result["logs"])
    finally:
        handlers._SESSION["gen"] = None
        Path(out.name).unlink(missing_ok=True)
