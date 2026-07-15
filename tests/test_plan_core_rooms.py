import plan_core
from plan_core import OperationPlanGenerator


MONDAY = "29.06.2026"


def event(title, time):
    return {
        "Название события": title,
        "Дата начала (МСК)": MONDAY,
        "Время начала (МСК)": time,
    }


def distribute(events, messages=None):
    generator = OperationPlanGenerator(
        events_data=events,
        log_callback=(
            (lambda message, tag="info": messages.append((message, tag)))
            if messages is not None
            else None
        ),
    )
    generator.parse_all_events()
    generator.distribute_patients()
    return generator


def test_narcosis_closure_keeps_before_and_moves_after_to_ma():
    generator = distribute(
        [
            event("Закрыто для наркоза", "12:00"),
            event("Иванов 30 септо", "11:00"),
            event("Петров 30 септо", "13:00"),
        ]
    )
    assert [patient["name"] for patient in generator.daily_blocks[0]["5"]] == ["Иванов"]
    assert [patient["name"] for patient in generator.daily_blocks[0]["MA"]] == ["Петров"]


def test_narcosis_closure_moves_tonsillectomy_after_time_to_room_seven():
    generator = distribute(
        [event("Закрыто для наркоза", "12:00"), event("Сидоров 20 тонзилэктомия", "13:00")]
    )
    assert [patient["name"] for patient in generator.daily_blocks[0]["7"]] == ["Сидоров"]


def test_typo_narcosis_closure_is_registered_and_applied():
    generator = distribute(
        [event("Зарыто для наркоза", "12:00"), event("Петров 30 септо", "13:00")]
    )
    assert generator.events_by_day[0][0]["type"] == "narcosis_closed"
    assert len(generator.daily_blocks[0]["MA"]) == 1


def test_generalochka_sends_non_tonsil_patients_to_ma_and_skips_tonsils():
    messages = []
    generator = distribute(
        [
            event("Генералочка", "08:00"),
            event("Иванов 30 септо", "10:00"),
            event("Петров 20 тонзилэктомия", "11:00"),
        ],
        messages,
    )
    assert [patient["name"] for patient in generator.daily_blocks[0]["MA"]] == ["Иванов"]
    assert not generator.daily_blocks[0]["5"]
    assert not generator.daily_blocks[0]["7"]
    assert any("тонзилэктомия отменена" in message for message, _ in messages)


def test_osteotomy_and_missing_age_defaults_are_business_values():
    generator = distribute(
        [
            event("Иванов септо остеотомия", "10:00"),
            event("Петров адено", "11:00"),
            event("Сидоров септо", "12:00"),
        ]
    )
    patients = generator.daily_blocks[0]["5"]
    assert patients[0]["operation"] == "Септопластика (остеотомия)"
    assert (patients[0]["age"], patients[0]["age_unit"]) == (44, "г")
    assert (patients[1]["age"], patients[1]["age_unit"]) == (5, "л")
    assert (patients[2]["age"], patients[2]["age_unit"]) == (44, "г")


def test_sorts_children_then_adults_then_unknown_age():
    generator = OperationPlanGenerator(events_data=[])
    generator.daily_blocks[0]["5"] = [
        {"age": 30}, {"age": 5}, {"age": None}, {"age": 3}, {"age": 44}
    ]
    generator.sort_patients_in_rooms()
    assert [patient["age"] for patient in generator.daily_blocks[0]["5"]] == [3, 5, 30, 44, None]


def test_invalid_closure_and_operation_times_log_warnings_and_keep_patient():
    messages = []
    generator = distribute(
        [
            event("Закрыто для наркоза", "not-a-time"),
            event("Иванов 30 септо", "also-bad"),
        ],
        messages,
    )
    assert [patient["name"] for patient in generator.daily_blocks[0]["5"]] == ["Иванов"]
    assert any("Некорректное время «закрыто" in message for message, _ in messages)
    assert any("некорректное время операции" in message for message, _ in messages)


def test_explicit_ma_tonsil_patient_goes_to_room_seven():
    generator = distribute([event("Иванов 30 М/А тонзилэктомия", "10:00")])
    # М/А — маркер наркоза, не часть ФИО
    assert [patient["name"] for patient in generator.daily_blocks[0]["7"]] == ["Иванов"]
    assert generator.daily_blocks[0]["7"][0]["is_ma"] is True


def test_assign_surgeons_reassigns_conflicting_ma_and_reports_conflicts(monkeypatch):
    messages = []
    generator = distribute(
        [
            event("Иванов 30 септо", "10:00"),
            event("Петров 30 М/А септо", "11:00"),
        ],
        messages,
    )
    monkeypatch.setattr(plan_core, "SURGEON_5", {day: "Доктор" for day in range(5)})
    monkeypatch.setattr(plan_core, "SURGEON_MA", {day: "Доктор" for day in range(5)})
    monkeypatch.setattr(plan_core, "FORBIDDEN_MA", [])
    # Остаётся №7 из расписания (или импортированный SURGEON_7)
    monkeypatch.setattr(plan_core, "SURGEON_7", "Запасной Х.Х.")
    generator.assign_surgeons()
    assert generator.daily_blocks[0]["MA"][0]["surgeon"] == "Запасной Х.Х."

    monkeypatch.setattr(plan_core, "SURGEON_7", "Доктор")
    generator.daily_blocks[0]["7"].append({"name": "Сидоров"})
    generator.assign_surgeons()
    assert any("Конфликт" in message for message, tag in messages if tag == "warning")
