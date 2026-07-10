import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import json
import os
import tempfile
from datetime import datetime, timedelta
from collections import Counter

from patient_parser import PatientParser, patient_parser
from plan_core import OperationPlanGenerator, is_service_event
from phone_extractor import extract_phones_from_events
import config_surgeons

# ----------------------------------------------------------------
#  Расширенные тесты дат и парсинга событий
# ----------------------------------------------------------------
class TestDateParsingExtended(unittest.TestCase):
    def test_date_without_time_column(self):
        """Дата без указания времени – событие всё равно должно парситься."""
        events = [
            {'Название события': 'Пациент 30 септо',
             'Дата начала (МСК)': '01.04.2026',
             'Время начала (МСК)': ''},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        self.assertEqual(len(gen.events_by_day[2]), 1)  # среда

    def test_iso_date_without_timezone(self):
        """2026-04-08T09:00:00 (без часового пояса) должен парситься."""
        events = [
            {'Название события': 'Пациент 10 адено',
             'Дата начала (МСК)': '2026-04-08T09:00:00',
             'Время начала (МСК)': '09:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        # 8 апреля 2026 – среда, индекс 2
        self.assertEqual(len(gen.events_by_day[2]), 1)

    def test_american_format_without_dayfirst(self):
        """03.04.2026 при dayfirst=True – всегда 3 апреля, не 4 марта."""
        events = [
            {'Название события': 'Пациент',
             'Дата начала (МСК)': '03.04.2026',
             'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        # Проверяем, что день недели пятница (weekday=4)
        self.assertIn(4, gen.events_by_day)
        self.assertEqual(len(gen.events_by_day[4]), 1)

    def test_date_with_extra_spaces(self):
        """Дата с пробелами и переносами – должна очищаться."""
        events = [
            {'Название события': 'Пациент',
             'Дата начала (МСК)': '  01.04.2026  ',
             'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        self.assertEqual(len(gen.events_by_day[2]), 1)

    def test_week_start_from_first_valid_event(self):
        """Неделя начинается с понедельника, вычисленного по первому событию."""
        events = [
            {'Название события': 'Первый', 'Дата начала (МСК)': '02.04.2026', 'Время начала (МСК)': '10:00'},  # четверг
            {'Название события': 'Второй', 'Дата начала (МСК)': '30.03.2026', 'Время начала (МСК)': '11:00'},  # понедельник раньше
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        # week_start должно быть равно понедельнику той недели, к которой относится первое событие (02.04 – четверг → понедельник 30.03)
        self.assertEqual(gen.week_start.date(), datetime(2026, 3, 30).date())

    def test_events_without_dates_dont_affect_week_start(self):
        """События без дат не должны влиять на week_start."""
        events = [
            {'Название события': 'Без даты', 'Дата начала (МСК)': '', 'Время начала (МСК)': '10:00'},
            {'Название события': 'С датой', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '11:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        self.assertIsNotNone(gen.week_start)
        # только второе событие добавится
        self.assertEqual(len(gen.events_by_day[2]), 1)

class TestEventParsingExtended(unittest.TestCase):
    def test_empty_title_skipped(self):
        """Событие с пустым названием пропускается."""
        events = [
            {'Название события': '', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        total = sum(len(gen.events_by_day[d]) for d in range(5))
        self.assertEqual(total, 0)

    def test_service_event_filtered_out(self):
        """Служебные события (каникулы) не добавляются в patients."""
        events = [
            {'Название события': 'Каникулы', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '00:00'},
            {'Название события': 'Пациент 10 Адено', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        # Только пациент, не каникулы
        patients = [e for e in gen.events_by_day[2] if 'name' in e]
        self.assertEqual(len(patients), 1)

    def test_generalochka_event_registered(self):
        """Генералочка добавляет день в generalochka_days и создаёт запись типа generalochka."""
        events = [
            {'Название события': 'Генералочка в операционной', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '08:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        self.assertIn(2, gen.generalochka_days)  # среда
        self.assertEqual(gen.events_by_day[2][0]['type'], 'generalochka')

    def test_narcosis_closed_event_creates_narcosis_closed_type(self):
        """Закрыто для наркоза создаёт запись с type='narcosis_closed'."""
        events = [
            {'Название события': 'закрыто для наркоза', 'Дата начала (МСК)': '02.04.2026', 'Время начала (МСК)': '12:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        # четверг
        self.assertEqual(gen.events_by_day[3][0]['type'], 'narcosis_closed')

    def test_multiple_generalochka_days(self):
        """Если генералочка указана в разные дни, все дни попадают в множество."""
        events = [
            {'Название события': 'Генералочка', 'Дата начала (МСК)': '30.03.2026', 'Время начала (МСК)': '08:00'},
            {'Название события': 'Генералочка', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '08:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        self.assertIn(0, gen.generalochka_days)  # пн
        self.assertIn(2, gen.generalochka_days)  # ср

    def test_log_warning_on_bad_date(self):
        """При некорректной дате вызывается log с warning."""
        warnings = []
        def log_cb(msg, tag='info'):
            if tag == 'warning':
                warnings.append(msg)
        events = [
            {'Название события': 'Пациент 10 Адено', 'Дата начала (МСК)': 'не дата', 'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events, log_callback=log_cb)
        gen.parse_all_events()
        self.assertEqual(len(warnings), 1)
        self.assertIn("Некорректная дата", warnings[0])
        self.assertIn("не дата", warnings[0])

    def test_no_warning_on_valid_date(self):
        """При корректной дате не должно быть warning-сообщений."""
        warnings = []
        def log_cb(msg, tag='info'):
            if tag == 'warning':
                warnings.append(msg)
        events = [
            {'Название события': 'Пациент 10 Адено', 'Дата начала (МСК)': '01.04.2026', 'Время начала (МСК)': '10:00'},
        ]
        gen = OperationPlanGenerator(events_data=events, log_callback=log_cb)
        gen.parse_all_events()
        self.assertEqual(len(warnings), 0)