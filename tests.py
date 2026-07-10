import unittest
from datetime import datetime, timedelta
import os, json, tempfile
from patient_parser import PatientParser, patient_parser
from plan_core import OperationPlanGenerator
from phone_extractor import extract_phones_from_events
import config_surgeons

# ----------------------------------------------------------------
#  1. PatientParser – извлечение возраста
# ----------------------------------------------------------------
class TestAgeExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = PatientParser()

    def test_age_years_short(self):
        age, unit, clean = self.parser.extract_age_and_clean("Иванов 7 л Адено")
        self.assertEqual(age, 7)
        self.assertEqual(unit, 'л')
        self.assertIn("Адено", clean)

    def test_age_none(self):
        age, unit, clean = self.parser.extract_age_and_clean("Иванов И.И. Тонзилэктомия")
        self.assertIsNone(age)
        self.assertIsNone(unit)

    def test_age_full_year_birth(self):
        age, unit, clean = self.parser.extract_age_and_clean("Сидоров 1980 г.р. Септо")
        expected_age = datetime.now().year - 1980
        self.assertEqual(age, expected_age)
        self.assertEqual(unit, 'л')
        self.assertIn("Септо", clean)

    def test_age_number_before_diag(self):
        age, unit, clean = self.parser.extract_age_and_clean("Петров 5 адено")
        self.assertEqual(age, 5)
        self.assertEqual(unit, 'л')
        self.assertIn("адено", clean.lower())

    def test_age_with_year_short(self):
        age, unit, clean = self.parser.extract_age_and_clean("Козлов 45 г.")
        self.assertEqual(age, 45)
        self.assertEqual(unit, 'г')

    def test_age_only_year_big(self):
        age, unit, clean = self.parser.extract_age_and_clean("Николаев 1950 г.р.")
        expected_age = datetime.now().year - 1950
        self.assertEqual(age, expected_age)
        self.assertEqual(unit, 'л')

    def test_age_empty_string(self):
        age, unit, clean = self.parser.extract_age_and_clean("")
        self.assertIsNone(age)
        self.assertIsNone(unit)

    def test_age_date_format(self):
        age, unit, clean = self.parser.extract_age_and_clean("Алексеев 15.03.2010")
        expected_age = datetime.now().year - 2010
        self.assertEqual(age, expected_age)
        self.assertEqual(unit, 'л')
        self.assertNotIn("15.03.2010", clean)

# ----------------------------------------------------------------
#  2. PatientParser – нормализация имени
# ----------------------------------------------------------------
class TestNameNormalization(unittest.TestCase):
    def setUp(self):
        self.parser = PatientParser()

    def test_simple_name(self):
        result = self.parser.normalize_name("иванов иван иванович")
        self.assertEqual(result, "Иванов Иван Иванович")

    def test_initials(self):
        result = self.parser.normalize_name("Петров А.В.")
        self.assertEqual(result, "Петров А.В.")

    def test_year_in_name(self):
        result = self.parser.normalize_name("Сидоров г.р. 1980")
        self.assertEqual(result, "Сидоров")

    def test_empty_name(self):
        result = self.parser.normalize_name("")
        self.assertEqual(result, "")

    def test_only_initials(self):
        result = self.parser.normalize_name("А.В.")
        self.assertEqual(result, "А.В.")

    def test_with_g_year(self):
        result = self.parser.normalize_name("Федоров г.р.")
        self.assertEqual(result, "Федоров")

# ----------------------------------------------------------------
#  3. PatientParser – классификация диагноза
# ----------------------------------------------------------------
class TestDiagnosisClassification(unittest.TestCase):
    def setUp(self):
        self.parser = PatientParser()

    def test_known_key(self):
        diag, oper = self.parser.get_diagnosis_and_operation("Адено")
        self.assertIn("Аденоиды", diag)
        self.assertIn("Аденотомия", oper)

    def test_unknown_returns_raw(self):
        diag, oper = self.parser.get_diagnosis_and_operation("Фантастический диагноз")
        self.assertEqual(diag, "Фантастический диагноз")
        self.assertEqual(oper, "Операция не указана")

    def test_combination_septo_vazo(self):
        diag, oper = self.parser.get_diagnosis_and_operation("септо вазо")
        self.assertIn("Искривление перегородки", diag)
        self.assertIn("Вазомоторный", diag)
        self.assertIn("Септопластика", oper)
        self.assertTrue("пластика раковин" in oper.lower())

    def test_combination_adeno_vr(self):
        diag, oper = self.parser.get_diagnosis_and_operation("А+ВР")
        self.assertIn("Аденоиды", diag)
        self.assertIn("Вазомоторный", diag)
        self.assertIn("Аденотомия", oper)
        self.assertIn("пластика раковин", oper)

    def test_septoplastika_only(self):
        diag, oper = self.parser.get_diagnosis_and_operation("септопластика")
        self.assertIn("Искривление перегородки", diag)
        self.assertIn("Септопластика", oper)

    def test_myringotomy(self):
        diag, oper = self.parser.get_diagnosis_and_operation("Миринго")
        self.assertIn("отит", diag)
        self.assertIn("Миринготомия", oper)

# ----------------------------------------------------------------
#  4. PatientParser – полный парсинг события
# ----------------------------------------------------------------
class TestPatientParserFull(unittest.TestCase):
    def setUp(self):
        self.parser = PatientParser()

    def test_full_event(self):
        patient = self.parser.parse_patient_from_event("Иванов 7 л Адено 89064014401", "")
        self.assertIsNotNone(patient)
        self.assertEqual(patient['name'], "Иванов")
        self.assertEqual(patient['age'], 7)
        self.assertIn("Аденотомия", self.parser.get_diagnosis_and_operation(patient['diagnosis_raw'])[1])

    def test_marked_ma(self):
        patient = self.parser.parse_patient_from_event("Петров 45 М/А Септо", "")
        self.assertIsNotNone(patient)
        self.assertTrue(patient['is_ma'])

    def test_osteotomy(self):
        patient = self.parser.parse_patient_from_event("Сидоров остеотомия септо", "")
        self.assertIsNotNone(patient)
        self.assertTrue(patient['has_osteotomy'])

    def test_unknown_diag_but_name(self):
        patient = self.parser.parse_patient_from_event("Шолохов вазо", "")
        self.assertIsNotNone(patient)
        self.assertFalse(patient.get('is_unknown_diag'))
        self.assertEqual(patient['name'], "Шолохов")

    def test_truly_unknown_diag(self):
        patient = self.parser.parse_patient_from_event("НеизвестныйДиагноз 30", "")
        self.assertIsNotNone(patient)
        self.assertTrue(patient.get('is_unknown_diag'))

    def test_service_event_not_ignored_by_parser(self):
        # Парсер не отсеивает служебные записи – это делает генератор
        patient = self.parser.parse_patient_from_event("Закрыто для наркоза", "")
        self.assertIsNotNone(patient)   # он создаёт пациента с неизвестным диагнозом
        self.assertTrue(patient.get('is_unknown_diag'))

    def test_empty_title(self):
        patient = self.parser.parse_patient_from_event("", "")
        self.assertIsNone(patient)

    def test_multiple_phones_preserved(self):
        patient = self.parser.parse_patient_from_event("Тестов 10 л Адено 89064014401 / 89296556228", "")
        self.assertIsNotNone(patient)
        self.assertEqual(patient['phones'], [])
        self.assertNotIn("890640", patient['diagnosis_raw'])

    def test_name_too_short_ignored(self):
        patient = self.parser.parse_patient_from_event("А. 5 л Адено", "")
        self.assertIsNone(patient)

# ----------------------------------------------------------------
#  5. OperationPlanGenerator
# ----------------------------------------------------------------
class TestOperationPlanGenerator(unittest.TestCase):
    def setUp(self):
        self.events = [
            {'Название события': 'Пациент1 30 септо', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '10:00'},
            {'Название события': 'Пациент2 25 вазо', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '11:00'},
            {'Название события': 'Генералочка в операционной', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '08:00'},
        ]

    def test_distribution_with_generalochka(self):
        gen = OperationPlanGenerator(events_data=self.events)
        gen.parse_all_events()
        self.assertEqual(len(gen.events_by_day[0]), 3)
        gen.distribute_patients()
        self.assertGreaterEqual(len(gen.daily_blocks[0]["MA"]), 2)

    def test_no_events(self):
        gen = OperationPlanGenerator(events_data=[])
        gen.parse_all_events()
        self.assertIsNone(gen.week_start)
        for day in range(5):
            self.assertEqual(len(gen.events_by_day[day]), 0)

    def test_narcosis_closed(self):
        events = [
            {'Название события': 'Закрыто для наркоза', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '12:00'},
            {'Название события': 'Пациент3 40 вазо', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '13:00'},
        ]
        gen = OperationPlanGenerator(events_data=events)
        gen.parse_all_events()
        gen.distribute_patients()
        self.assertEqual(len(gen.daily_blocks[0]["MA"]), 1)

# ----------------------------------------------------------------
#  6. config_surgeons
# ----------------------------------------------------------------
class TestSurgeonConfig(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.mktemp(suffix='.json')
        config_surgeons.SURGEON_CONFIG_FILE = self.temp_file
        config_surgeons.SURGEON_5, config_surgeons.SURGEON_7, config_surgeons.SURGEON_MA, config_surgeons.FORBIDDEN_MA = \
            config_surgeons.DEFAULT_SURGEON_5.copy(), config_surgeons.DEFAULT_SURGEON_7, \
            config_surgeons.DEFAULT_SURGEON_MA.copy(), config_surgeons.DEFAULT_FORBIDDEN_MA.copy()

    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def test_default_values(self):
        surg5, surg7, surgMA, forbidden = config_surgeons.load_surgeons()
        self.assertEqual(surg5[0], "Баганов Д.Г.")
        self.assertEqual(surg7, "Доронина Н.С.")
        self.assertIn("Салихов Д.А.", forbidden)

    def test_save_and_reload(self):
        new_surg5 = {0: "Новый Хирург", 1: "Гасанов М.Т.", 2: "Карибова С.О.", 3: "Салихов Д.А.", 4: "Гасанов М.Т."}
        new_surg7 = "Другой Хирург"
        new_surgMA = {0: "Карибова С.О.", 1: "Новый Хирург", 2: "Гасанов М.Т.", 3: "Карибова С.О.", 4: "Баганов Д.Г."}
        new_forbidden = ["Салихов Д.А."]
        config_surgeons.save_surgeons(new_surg5, new_surg7, new_surgMA, new_forbidden)
        s5, s7, sMA, f = config_surgeons.load_surgeons()
        self.assertEqual(s5[0], "Новый Хирург")
        self.assertEqual(s7, "Другой Хирург")
        self.assertEqual(f, ["Салихов Д.А."])

# ----------------------------------------------------------------
#  7. phone_extractor
# ----------------------------------------------------------------
class TestPhoneExtractor(unittest.TestCase):
    def test_extract_phones(self):
        events = [
            {'Название события': 'Иванов 7 л Адено 89064014401', 'Описание': ''},
            {'Название события': 'Закрыто для наркоза', 'Описание': ''},
            {'Название события': 'Петров 30 Септо 79001234567', 'Описание': ''},   # слитный номер
        ]
        result = extract_phones_from_events(events)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ('79064014401', 'Иванов'))
        self.assertEqual(result[1], ('79001234567', 'Петров'))

if __name__ == '__main__':
    unittest.main()