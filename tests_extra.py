import unittest
from datetime import datetime, timedelta
import os, json, tempfile
from patient_parser import PatientParser, patient_parser
from plan_core import OperationPlanGenerator, is_service_event
from phone_extractor import extract_phones_from_events
import config_surgeons
from collections import Counter

# ----------------------------------------------------------------
#  Дополнительные тесты для PatientParser
# ----------------------------------------------------------------
class TestPatientParserExtra(unittest.TestCase):
    def setUp(self):
        self.parser = PatientParser()

    # --- sanitize_text ---
    def test_sanitize_removes_nbsp(self):
        text = "Иванов\u00A07\xa0лет"
        clean = self.parser.sanitize_text(text)
        self.assertEqual(clean, "Иванов 7 лет")

    def test_sanitize_collapses_spaces(self):
        clean = self.parser.sanitize_text("   много   пробелов   ")
        self.assertEqual(clean, "много пробелов")

    # --- clean_phone_numbers ---
    def test_clean_phones_removes_russian_format(self):
        text = "Петров 89064014401"
        cleaned = self.parser.clean_phone_numbers(text)
        self.assertNotIn("89064014401", cleaned)

    def test_clean_phones_removes_international(self):
        text = "Сидоров +7(906)401-44-01"
        cleaned = self.parser.clean_phone_numbers(text)
        self.assertNotIn("+7", cleaned)
        self.assertNotIn("906", cleaned)

    def test_clean_phones_preserves_other_text(self):
        text = "Иванов Адено 89064014401"
        cleaned = self.parser.clean_phone_numbers(text)
        self.assertIn("Иванов", cleaned)
        self.assertIn("Адено", cleaned)

    # --- get_surname_and_initials ---
    def test_surname_and_initials_simple(self):
        surname, initials = self.parser.get_surname_and_initials("Иванов Иван Иванович")
        self.assertEqual(surname, "Иванов")
        self.assertEqual(initials, "И.И.")

    def test_surname_and_initials_with_dot(self):
        surname, initials = self.parser.get_surname_and_initials("Петров А.В.")
        self.assertEqual(surname, "Петров")
        self.assertEqual(initials, "А.В.")

    def test_surname_only(self):
        surname, initials = self.parser.get_surname_and_initials("Сидоров")
        self.assertEqual(surname, "Сидоров")
        self.assertEqual(initials, "")

    # --- build_display_name ---
    def test_display_name_unique_surname(self):
        counter = Counter(["Иванов"])
        display = self.parser.build_display_name("Иванов Иван", counter)
        self.assertEqual(display, "Иванов")

    def test_display_name_duplicate_surname(self):
        counter = Counter(["Петров", "Петров"])
        display = self.parser.build_display_name("Петров И.И.", counter)
        self.assertEqual(display, "Петров И.И.")

    def test_display_name_no_initials_duplicate(self):
        counter = Counter(["Сидоров", "Сидоров"])
        display = self.parser.build_display_name("Сидоров", counter)
        self.assertEqual(display, "Сидоров")

    # --- resolve_age_defaults ---
    def test_age_default_for_child_diag(self):
        age, unit = self.parser.resolve_age_defaults("Аденоиды", None)
        self.assertEqual(age, 5)
        self.assertEqual(unit, 'л')

    def test_age_default_for_adult_diag(self):
        age, unit = self.parser.resolve_age_defaults("Септопластика", None)
        self.assertEqual(age, 44)
        self.assertEqual(unit, 'г')

    def test_age_default_preserves_given_age(self):
        age, unit = self.parser.resolve_age_defaults("что-то", 10)
        self.assertEqual(age, 10)
        self.assertEqual(unit, 'л')  # возраст < 18 -> 'л'

    def test_age_default_preserves_given_age_adult(self):
        age, unit = self.parser.resolve_age_defaults("что-то", 45)
        self.assertEqual(age, 45)
        self.assertEqual(unit, 'г')

    # --- get_diagnosis_and_operation: дополнительные комбинации ---
    def test_septo_vazo_and_uvulo(self):
        diag, oper = self.parser.get_diagnosis_and_operation("септо вазо увуло")
        self.assertIn("Ронхопатия", diag)
        self.assertIn("увулопластика", oper.lower())

    def test_septo_and_polyp(self):
        diag, oper = self.parser.get_diagnosis_and_operation("септо полип")
        self.assertIn("Полип", diag)
        self.assertIn("удаление полипа", oper.lower())

    def test_septo_and_papilloma_tonsil(self):
        diag, oper = self.parser.get_diagnosis_and_operation("септо папилома миндалины")
        self.assertIn("Образование миндалины", diag)
        self.assertIn("удаление образования", oper.lower())

    def test_adeno_plus_miringo(self):
        diag, oper = self.parser.get_diagnosis_and_operation("А+М")
        self.assertIn("Аденоиды", diag)
        self.assertIn("отит", diag)
        self.assertIn("миринготомия", oper.lower())

    def test_polysinusotomy(self):
        diag, oper = self.parser.get_diagnosis_and_operation("полисинусотомия")
        self.assertIn("Хронический синусит", diag)
        self.assertIn("Полисинусотомия", oper)

    def test_uvulopalatoplasty(self):
        diag, oper = self.parser.get_diagnosis_and_operation("увулопалато")
        self.assertIn("Ронхопатия", diag)
        self.assertIn("Увулопластика", oper)

# ----------------------------------------------------------------
#  Тесты служебной функции is_service_event
# ----------------------------------------------------------------
class TestServiceEventDetection(unittest.TestCase):
    def test_narcosis_closed(self):
        self.assertTrue(is_service_event("Закрыто для наркоза"))
        self.assertTrue(is_service_event("Закрыто  для  наркоза"))  # пробелы
        self.assertTrue(is_service_event("Зарыто для наркоза"))     # опечатка

    def test_generalochka(self):
        self.assertTrue(is_service_event("Генералочка в операционной"))

    def test_kanikuli(self):
        self.assertTrue(is_service_event("Каникулы"))

    def test_dlya_so(self):
        self.assertTrue(is_service_event("для сотрудников"))

    def test_patient_not_service(self):
        self.assertFalse(is_service_event("Иванов 7 л Адено"))

# ----------------------------------------------------------------
#  Дополнительные тесты для OperationPlanGenerator
# ----------------------------------------------------------------
class TestOperationPlanGeneratorExtra(unittest.TestCase):
    def setUp(self):
        # Простой набор пациентов для теста сортировки
        self.patients = [
            {"name": "Взрослый1", "age": 30, "age_unit": "г", "diagnosis": "Септо", "operation": "Септопластика"},
            {"name": "Ребёнок1", "age": 5, "age_unit": "л", "diagnosis": "Адено", "operation": "Аденотомия"},
            {"name": "Ребёнок2", "age": 3, "age_unit": "г", "diagnosis": "Адено", "operation": "Аденотомия"},
            {"name": "Взрослый2", "age": 44, "age_unit": "г", "diagnosis": "Вазо", "operation": "Пластика раковин"},
        ]

    def test_sort_patients_children_first_by_age(self):
        gen = OperationPlanGenerator(events_data=[])
        gen.daily_blocks[0]["5"] = self.patients.copy()
        gen.sort_patients_in_rooms()
        sorted_ages = [p['age'] for p in gen.daily_blocks[0]["5"]]
        # Ожидаем: дети по возрастанию (3,5), затем взрослые (30,44)
        self.assertEqual(sorted_ages, [3, 5, 30, 44])

    def test_sort_with_none_age_at_end(self):
        patients_with_none = self.patients + [{"name": "Неизв", "age": None, "age_unit": "", "diagnosis": "", "operation": ""}]
        gen = OperationPlanGenerator(events_data=[])
        gen.daily_blocks[0]["5"] = patients_with_none
        gen.sort_patients_in_rooms()
        self.assertIsNone(gen.daily_blocks[0]["5"][-1]['age'])

    def test_assign_surgeons_logs_conflict(self):
        # Создаём ситуацию, когда один хирург назначен в две операционные
        import config_surgeons as cs
        # Сохраним старые значения, чтобы восстановить
        old_5 = cs.SURGEON_5.copy()
        old_ma = cs.SURGEON_MA.copy()
        try:
            # Делаем так, чтобы в один день SURGEON_5 и SURGEON_MA совпадали
            cs.SURGEON_5[0] = "Доктор А"
            cs.SURGEON_MA[0] = "Доктор А"   # одинаковый хирург -> конфликт
            gen = OperationPlanGenerator(events_data=[
                {'Название события': 'Пациент 30 септо', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '10:00'},
                {'Название события': 'Пациент 25 вазо', 'Дата начала (МСК)': '29.06.2026', 'Время начала (МСК)': '11:00'},
            ])
            gen.parse_all_events()
            gen.distribute_patients()
            # Подменяем log-колбэк, чтобы поймать сообщение
            warnings = []
            gen.log = lambda msg, tag='info': warnings.append(msg) if tag == 'warning' else None
            gen.assign_surgeons()
            self.assertTrue(any("Конфликт" in w for w in warnings))
        finally:
            cs.SURGEON_5 = old_5
            cs.SURGEON_MA = old_ma

# ----------------------------------------------------------------
#  Дополнительный тест phone_extractor
# ----------------------------------------------------------------
class TestPhoneExtractorExtra(unittest.TestCase):
    def test_phone_in_description(self):
        events = [
            {'Название события': 'Иванов', 'Описание': '89064014401'},
            {'Название события': 'Петров', 'Описание': 'нет номера'},
        ]
        result = extract_phones_from_events(events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ('79064014401', 'Иванов'))

    def test_multiple_phones_one_patient(self):
        events = [
            {'Название события': 'Сидоров 89261234567', 'Описание': 'доп. 89064014401'},
        ]
        result = extract_phones_from_events(events)
        self.assertEqual(len(result), 1)   # функция берёт первый найденный номер в объединённом тексте
        # Номер преобразован: 8926... -> 7926...
        self.assertIn('79261234567', result[0][0])

# ----------------------------------------------------------------
#  Тест config_surgeons при отсутствии файла
# ----------------------------------------------------------------
class TestSurgeonConfigFileMissing(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.mktemp(suffix='.json')
        # Гарантируем, что файла нет
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
        config_surgeons.SURGEON_CONFIG_FILE = self.temp_file

    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def test_load_returns_defaults_when_file_missing(self):
        surg5, surg7, surgMA, forbidden = config_surgeons.load_surgeons()
        self.assertEqual(surg5[0], "Баганов Д.Г.")
        self.assertEqual(surg7, "Доронина Н.С.")
        self.assertIn("Салихов Д.А.", forbidden)

if __name__ == '__main__':
    unittest.main()