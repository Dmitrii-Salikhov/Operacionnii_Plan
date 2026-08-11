"""Review room reassignment on plan.export."""

import tempfile
from pathlib import Path

from plan_core import OperationPlanGenerator
from bridge import handlers


def _patient(**kwargs):
    base = {
        "name": "Иванов",
        "age": 30,
        "age_unit": "л",
        "diagnosis_raw": "непонятная операция",
        "diagnosis": "Диагноз не указан",
        "operation": "Операция не указана",
        "is_unknown_diag": True,
        "needs_name_review": False,
        "confidence": 0.0,
        "is_ma": False,
        "is_etn": False,
        "has_osteotomy": False,
        "phones": [],
        "full_text": "",
        "time": "10:00",
    }
    base.update(kwargs)
    return base


def test_collect_reviews_includes_current_room():
    gen = OperationPlanGenerator(events_data=[])
    gen.daily_blocks[0]["5"] = [_patient(name="В пятой")]
    gen.daily_blocks[0]["7"] = [_patient(name="В седьмой")]
    gen.daily_blocks[0]["MA"] = [_patient(name="В МА")]

    rows = handlers._collect_reviews(gen)
    by_name = {r["name"]: r for r in rows}
    assert by_name["В пятой"]["room"] == "5"
    assert by_name["В седьмой"]["room"] == "7"
    assert by_name["В МА"]["room"] == "MA"


def test_apply_review_room_moves_patient_between_rooms():
    gen = OperationPlanGenerator(events_data=[])
    patient = _patient(name="Сидоров")
    gen.daily_blocks[1]["5"] = [patient]
    handlers._collect_reviews(gen)
    rid = patient["_bridge_id"]

    logs = []
    handlers._apply_review_room_moves(
        gen,
        {rid: {"id": rid, "room": "7"}},
        log_cb=lambda msg, tag="info": logs.append(msg),
    )

    assert patient not in gen.daily_blocks[1]["5"]
    assert gen.daily_blocks[1]["7"] == [patient]
    assert any("Сидоров → операционная 7" in m for m in logs)


def test_apply_review_room_ignores_same_or_invalid_room():
    gen = OperationPlanGenerator(events_data=[])
    patient = _patient(name="Петров")
    gen.daily_blocks[0]["MA"] = [patient]
    handlers._collect_reviews(gen)
    rid = patient["_bridge_id"]

    handlers._apply_review_room_moves(gen, {rid: {"id": rid, "room": "MA"}})
    assert gen.daily_blocks[0]["MA"] == [patient]

    handlers._apply_review_room_moves(gen, {rid: {"id": rid, "room": "99"}})
    assert gen.daily_blocks[0]["MA"] == [patient]


def test_plan_export_moves_room_from_reviews():
    from datetime import date

    gen = OperationPlanGenerator(events_data=[])
    gen.week_start = date(2026, 6, 29)
    patient = _patient(name="Козлов", diagnosis="Хронический тонзиллит", operation="Тонзилэктомия")
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
                        "name": "Козлов",
                        "diagnosis": "Хронический тонзиллит",
                        "operation": "Тонзилэктомия",
                        "room": "7",
                        "remember": False,
                    }
                ],
            }
        )
        assert Path(result["output_path"]).exists()
        assert patient not in gen.daily_blocks[0]["5"]
        assert patient in gen.daily_blocks[0]["7"]
        assert any(
            "Козлов → операционная 7" in row["message"] for row in result["logs"]
        )
    finally:
        handlers._SESSION["gen"] = None
        Path(out.name).unlink(missing_ok=True)
