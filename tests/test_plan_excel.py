from openpyxl import load_workbook

from constants import WEEKDAYS_FULL
from plan_core import OperationPlanGenerator


def test_generate_excel_creates_weekday_and_admission_sheets(tmp_path):
    generator = OperationPlanGenerator(
        events_data=[
            {
                "Название события": "Иванов Иван 30 септо",
                "Дата начала (МСК)": "29.06.2026",
                "Время начала (МСК)": "10:00",
            },
            {
                "Название события": "Петров 8 адено",
                "Дата начала (МСК)": "30.06.2026",
                "Время начала (МСК)": "11:00",
            },
        ]
    )
    generator.parse_all_events()
    generator.distribute_patients()
    generator.assign_surgeons()
    generator.sort_patients_in_rooms()
    output = tmp_path / "plan.xlsx"
    assert generator.generate_excel(output) is True
    assert output.stat().st_size > 0
    workbook = load_workbook(output)
    assert set(WEEKDAYS_FULL).issubset(workbook.sheetnames)
    assert "Поступление" in workbook.sheetnames
