import re
import json
import os
from datetime import datetime
from collections import Counter
from typing import Optional, Tuple, Dict, Any, List

class PatientParser:
    def __init__(self, diagnosis_map: Optional[Dict[str, Tuple[str, str]]] = None,
                 custom_diag_file: str = 'custom_diagnoses.json'):
        if diagnosis_map is not None:
            self.diagnosis_map = diagnosis_map
        else:
            self.diagnosis_map = {
                "Адено": ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия"),
                "АТ": ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия"),
                "Адено+Т-Э": ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия"),
                "ГНМ": ("J35.2 Гипертрофия небных миндалин 2-3 ст", "Тонзиллотомия"),
                "тонзилотомия": ("J35.2 Гипертрофия небных миндалин 2-3 ст", "Тонзиллотомия"),
                "аденотонзилло": ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия"),
                "аденоиды": ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия"),
                "Т/э": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "Т-Э": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "тонз": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "т/эктом": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "тэ": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "тонзилэктомия": ("J35 Хронический тонзиллит", "Тонзилэктомия"),
                "А+Т-Э": ("J35.2 Аденоиды, ГНМ, J35 Хронический тонзиллит", "Аденотомия, тонзилэктомия"),
                "Миринго": ("H65 Хронический средний серозный отит", "Миринготомия"),
                "А+М": ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия"),
                "Адено+М": ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия"),
                "ат меринго": ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия"),
                "ат, меринго": ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия"),
                "Полисинусо": ("J32 Хронический синусит", "Полисинусотомия"),
                "полисинусотомия": ("J32 Хронический синусит", "Полисинусотомия"),
                "гайморо": ("J32 Хронический синусит", "Гайморотомия"),
                "гайморотомия": ("J32 Хронический синусит", "Гайморотомия"),
                "решетки": ("J32 Хронический синусит", "Гайморотомия"),
                "этмоидо": ("J32 Хронический синусит, этмоидит", "Полисинусотомия с этмоидотомией"),
                "антрохоанальный полип": ("J33.1 Полипозный риносинусит", "Гайморотомия с удалением полипа"),
                "Септо": ("J34.2 Искривление перегородки носа", "Септопластика"),
                "септ": ("J34.2 Искривление перегородки носа", "Септопластика"),
                "септопластика": ("J34.2 Искривление перегородки носа", "Септопластика"),
                "Вазо": ("J30.0 Вазомоторный ринит", "Пластика раковин"),
                "ВР": ("J30.0 Вазомоторный ринит", "Пластика раковин"),
                "вазотомия": ("J30.0 Вазомоторный ринит", "Пластика раковин"),
                "конхо": ("J30.0 Вазомоторный ринит", "Пластика раковин"),
                "конхобуллез": ("J30.0 Вазомоторный ринит", "Пластика раковин"),
                "Полип": ("J33 Полип полости носа", "Удаление полипа"),
                "Папиллома язычка": ("D14 Образование глотки", "Удаление образования глотки"),
                "Увуло": ("J31.2 Ронхопатия", "Увулопластика"),
                "увулопалато": ("J31.2 Ронхопатия", "Увулопластика"),
                "увулопластика": ("J31.2 Ронхопатия", "Увулопластика"),
                "Липома уха": ("D14 Образование уха", "Удаление образования"),
                "Обр-ние миндалины": ("D14 Образование миндалины", "Удаление образования"),
                "Синехии": ("J34.8 Синехии носа", "Синехотомия"),
                "киста в/ч пазухи": ("J34.0 Киста верхнечелюстной пазухи", "Гайморотомия"),
                "Хрон синусит": ("J32 Хронический синусит", "Гайморотомия"),
                "Перфорация перегородки носа": ("J34.8 Перфорация перегородки носа", "Пластика перфорации перегородки"),
                "Перфорация перегородки": ("J34.8 Перфорация перегородки носа", "Пластика перфорации перегородки"),
                "Атерома мочки уха": ("D14 Образование уха", "Удаление образования"),
                "привесок уха": ("D14 Образование уха", "Удаление образования"),
                "привеска уха": ("D14 Образование уха", "Удаление образования"),
                "привеску уха": ("D14 Образование уха", "Удаление образования"),
                "привеском уха": ("D14 Образование уха", "Удаление образования"),
                "привеске уха": ("D14 Образование уха", "Удаление образования"),
                "удаление привеска уха": ("D14 Образование уха", "Удаление образования"),
                "удаление привеску уха": ("D14 Образование уха", "Удаление образования"),
                "А+ВР": ("J35.2 Аденоиды, ГНМ, J30.0 Вазомоторный ринит", "Аденотомия, тонзиллотомия, пластика раковин"),
                "Адено+ВР": ("J35.2 Аденоиды, ГНМ, J30.0 Вазомоторный ринит", "Аденотомия, тонзиллотомия, пластика раковин"),
                "Ат-вазо": ("J35.2 Аденоиды, ГНМ, J30.0 Вазомоторный ринит", "Аденотомия, тонзиллотомия, пластика раковин"),
                "Адено вазо": ("J35.2 Аденоиды, ГНМ, J30.0 Вазомоторный ринит", "Аденотомия, тонзиллотомия, пластика раковин"),
                "Вазо синехии": ("J30.0 Вазомоторный ринит, J34.8 Синехии носа", "Пластика раковин, синехотомия"),
                "септо полип": ("J34.2 Искривление перегородки носа, J33 Полип полости носа", "Септопластика, удаление полипа"),
                "септо папилома миндалины": ("J34.2 Искривление перегородки носа, D14 Образование миндалины", "Септопластика, удаление образования миндалины"),
            }
        self.custom_diag_file = custom_diag_file
        self.load_custom_diagnoses()
        self.sort_keys()

    def load_custom_diagnoses(self):
        if os.path.exists(self.custom_diag_file):
            with open(self.custom_diag_file, 'r', encoding='utf-8') as f:
                custom = json.load(f)
            for key, (diag, op) in custom.items():
                self.diagnosis_map[key] = (diag, op)

    def save_custom_diagnosis(self, key: str, diag: str, operation: str):
        custom = {}
        if os.path.exists(self.custom_diag_file):
            with open(self.custom_diag_file, 'r', encoding='utf-8') as f:
                custom = json.load(f)
        custom[key] = (diag, operation)
        with open(self.custom_diag_file, 'w', encoding='utf-8') as f:
            json.dump(custom, f, ensure_ascii=False, indent=2)
        self.diagnosis_map[key] = (diag, operation)
        self.sort_keys()

    def save_custom_diagnoses_full(self):
        with open(self.custom_diag_file, 'w', encoding='utf-8') as f:
            json.dump(self.diagnosis_map, f, ensure_ascii=False, indent=2)

    def sort_keys(self):
        self.sorted_keys = sorted(self.diagnosis_map.keys(), key=lambda k: len(k), reverse=True)

    # ---------- Методы извлечения ----------
    def extract_age_and_clean(self, text: str) -> Tuple[Optional[int], Optional[str], str]:
        # Дата рождения в формате ДД.ММ.ГГГГ
        m_date = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if m_date:
            day, month, year = map(int, m_date.groups())
            try:
                birth_date = datetime(year, month, day)
                today = datetime.now()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                clean = text[:m_date.start()] + text[m_date.end():]
                clean = re.sub(r'\s*г\.?\s*р?\.?\s*$', '', clean).strip()
                return age, 'л', clean
            except:
                pass

        # Возраст с указанием единицы (л, лет, год, г)
        m = re.search(r'(\d+)\s*(л|лет|год|года|г)\.?(?=\s|$)', text, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            unit_raw = m.group(2).lower()
            unit = 'л' if 'л' in unit_raw else 'г'
            if num > 120:
                birth_year = num
                today = datetime.now()
                age = today.year - birth_year
                clean = text[:m.start()] + text[m.end():]
                clean = re.sub(r'\s*г\.?\s*$', '', clean).strip()
                return age, 'л', clean
            clean = text[:m.start()] + text[m.end():]
            clean = re.sub(r'\s\.\s', ' ', clean).strip()
            clean = re.sub(r'^\s*\.\s*', '', clean).strip()
            return num, unit, clean.strip()

        # Год рождения в формате "1980 г.р."
        m = re.search(r'(\d{4})\s*г\.?\s*р?\.?', text, re.IGNORECASE)
        if m:
            birth_year = int(m.group(1))
            today = datetime.now()
            age = today.year - birth_year
            clean = text[:m.start()] + text[m.end():]
            clean = clean.strip()
            return age, 'л', clean

        # Возраст перед ключевыми диагнозами
        DIAG_TERMS = [
            'тонз', 'т/э', 'т/эктом', 'септо', 'адено', 'ат', 'гнм', 'миринго',
            'вазо', 'вр', 'полип', 'гайморо', 'решетки', 'синехии', 'атерома',
            'липома', 'увуло', 'папиллома', 'перфорация', 'полисинусо', 'хрон', 'киста'
        ]
        pattern = r'(\d+)\s+(?=(?:' + '|'.join(DIAG_TERMS) + r')\b)'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            clean = text[:m.start()] + text[m.end():]
            return age, 'л', clean.strip()
        return None, None, text

    def normalize_name(self, raw_name: str) -> str:
        if not raw_name:
            return raw_name
        name = re.sub(r'[^а-яёА-ЯЁa-zA-Z\. ]', ' ', raw_name)
        name = re.sub(r'\s+', ' ', name).strip()
        parts = name.split()
        out = []
        for p in parts:
            # Удаляем фрагменты "г.р.", "г.р", "гр."
            if re.fullmatch(r'г\.?р?\.?', p, re.IGNORECASE):
                continue
            if re.fullmatch(r'г\.?', p, re.IGNORECASE):
                continue
            if re.match(r'^[а-яёa-z]\.?[а-яёa-z]?\.?$', p, re.IGNORECASE):
                out.append(p.upper().replace('.', '.') if '.' in p else p.upper() + '.')
            else:
                out.append(p.capitalize())
        return ' '.join(out)

    def get_surname_and_initials(self, full_name: str) -> Tuple[str, str]:
        parts = full_name.split()
        if not parts:
            return '', ''
        surname = parts[0]
        initials = []
        for part in parts[1:]:
            if re.match(r'^[А-ЯЁA-Z]\.[А-ЯЁA-Z]?\.?$', part):
                initials.append(part.rstrip('.'))
            elif len(part) > 1 and not re.match(r'^[А-ЯЁA-Z]\.', part):
                initials.append(part[0].upper())
        initials_str = '.'.join(initials) + '.' if initials else ''
        return surname, initials_str

    def build_display_name(self, full_name: str, surname_counter: Counter) -> str:
        surname, initials = self.get_surname_and_initials(full_name)
        if surname_counter[surname] > 1 and initials:
            return f"{surname} {initials}"
        return surname

    def clean_phone_numbers(self, text: str) -> str:
        text = re.sub(r'\+?\d{1,3}\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}', ' ', text)
        text = re.sub(r'[78]\d{10}', ' ', text)
        return text

    def sanitize_text(self, text: str) -> str:
        text = re.sub(r'[\u00A0\u200B-\u200F\u2028-\u202F\uFEFF]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def parse_patient_from_event(self, title: str, description: str, logger=None) -> Optional[Dict[str, Any]]:
        title = str(title).replace('nan', '') if title else ''
        description = str(description).replace('nan', '') if description else ''
        full_text = f"{title} {description}".strip()
        if logger:
            logger(f"[ИСХОДНАЯ] {full_text}")
        full_text = self.sanitize_text(full_text)
        full_text = self.clean_phone_numbers(full_text)
        clean = re.sub(r'\s+', ' ', full_text).strip()
        if logger:
            logger(f"[БЕЗ ТЕЛЕФОНОВ] {clean}")
        if not clean:
            return None

        is_ma = bool(re.search(r'\b[Мм]/[Аа]\b', clean))
        is_etn = bool(re.search(r'\bЭТН\b', clean, re.IGNORECASE))
        if not is_ma and not is_etn:
            is_etn = True

        has_osteotomy = bool(re.search(r'остеотоми[яи]', clean, re.IGNORECASE))

        age, unit, clean = self.extract_age_and_clean(clean)
        if logger:
            logger(f"[ПОСЛЕ ИЗВЛ. ВОЗРАСТА] age={age}, unit={unit}, clean='{clean}'")

        clean = re.sub(r'\bг\.?\b', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if not clean:
            return None

        best_idx = len(clean)
        best_key = None
        for key in self.sorted_keys:
            if len(key) <= 2:
                pattern = r'\b' + re.escape(key) + r'\b'
                match = re.search(pattern, clean, re.IGNORECASE)
                if match:
                    idx = match.start()
                    if idx < best_idx:
                        best_idx = idx
                        best_key = key
            else:
                idx = clean.lower().find(key.lower())
                if idx != -1 and idx < best_idx:
                    best_idx = idx
                    best_key = key

        def has_diag_key_in_brackets(match):
            content = match.group(1)
            for k in self.diagnosis_map:
                if k.lower() in content.lower():
                    return True
            return False

        clean_for_search = re.sub(r'\(([^)]+)\)',
                                  lambda m: ' ' + m.group(1) + ' ' if has_diag_key_in_brackets(m) else ' ',
                                  clean)
        if best_key is None:
            for key in self.sorted_keys:
                idx = clean_for_search.lower().find(key.lower())
                if idx != -1:
                    best_key = key
                    best_idx = idx
                    break

        is_unknown_diag = False
        if best_key is None:
            name_part = clean.strip()
            diag_part = ''
            is_unknown_diag = True
        else:
            idx_in_clean = clean.lower().find(best_key.lower())
            if idx_in_clean == -1:
                name_part = clean.split(best_key, 1)[0].strip()
                diag_part = best_key + clean.split(best_key, 1)[1] if len(clean.split(best_key, 1)) > 1 else best_key
            else:
                name_part = clean[:idx_in_clean].strip()
                diag_part = clean[idx_in_clean:].strip()

        if logger:
            logger(f"[ИМЯ/ДИАГНОЗ] name_part='{name_part}', diag_part='{diag_part}'")

        name_part = re.sub(r'\(.*?\)', '', name_part)
        name_part = name_part.replace('...', '').replace('…', '')
        name_part = name_part.strip('. ')
        patient_name = self.normalize_name(name_part)
        if logger:
            logger(f"[ПОСЛЕ normalize_name] '{patient_name}'")

        if len(patient_name.replace('.', '').strip()) <= 2:
            if logger:
                logger(f"[ИГНОРИРОВАНО] Имя слишком короткое: '{patient_name}'")
            return None

        def preserve_diag_in_brackets(match):
            content = match.group(1)
            for k in self.diagnosis_map:
                if k.lower() in content.lower():
                    return ' ' + content + ' '
            return ' '

        diag_part_clean = re.sub(r'\(([^)]+)\)', preserve_diag_in_brackets, diag_part)
        diag_part_clean = re.sub(r'[?]+', '', diag_part_clean).strip()
        diag_part_clean = re.sub(r'\bбулла\b', '', diag_part_clean, flags=re.IGNORECASE).strip()
        if not diag_part_clean and not is_unknown_diag:
            return None

        if logger:
            logger(f"[ФИНАЛ] name='{patient_name}', age={age}, diag_raw='{diag_part_clean}'\n")

        return {
            "name": patient_name,
            "age": age,
            "age_unit": unit if unit else ('г' if age and 1 <= age <= 4 else 'л'),
            "diagnosis_raw": diag_part_clean,
            "is_ma": is_ma,
            "is_etn": is_etn,
            "has_osteotomy": has_osteotomy,
            "is_unknown_diag": is_unknown_diag,
            "phones": [],
            "full_text": full_text,
        }

    def get_diagnosis_and_operation(self, diag_raw: str) -> Tuple[str, str]:
        low = diag_raw.strip().lower()
        # Полный список комбинаций
        if "септо" in low and ("вр" in low or "вазо" in low) and ("гайм" in low or "пазух" in low or "синусит" in low):
            return ("J34.2 Искривление перегородки носа, J30.0 Вазомоторный ринит, J32 Хронический синусит",
                    "Септопластика, пластика раковин, гайморотомия")
        if "септо" in low and ("вр" in low or "вазо" in low) and "увуло" in low:
            return ("J34.2 Искривление перегородки носа, J30.0 Вазомоторный ринит, J31.2 Ронхопатия",
                    "Септопластика, пластика раковин, увулопластика")
        if "септо" in low and ("вр" in low or "вазо" in low) and ("адено" in low or "аденоиды" in low):
            return ("J34.2 Искривление перегородки носа, J30.0 Вазомоторный ринит, J35.2 Аденоиды, ГНМ",
                    "Септопластика, пластика раковин, аденотомия, тонзиллотомия")
        if "септо" in low and ("вр" in low or "вазо" in low) and "киста" in low:
            return ("J34.2 Искривление перегородки носа, J30.0 Вазомоторный ринит, J34.0 Киста верхнечелюстной пазухи",
                    "Септопластика, пластика раковин, гайморотомия")
        if "септо" in low and "тонзилэктомия" in low and "увулопластика" in low:
            return ("J34.2 Искривление перегородки носа, J35 Хронический тонзиллит, J31.2 Ронхопатия",
                    "Септопластика, тонзилэктомия, увулопластика")
        if "септо" in low and "полисинусотомия" in low:
            return ("J34.2 Искривление перегородки носа, J32 Хронический синусит",
                    "Септопластика, полисинусотомия")
        if "септо" in low and "увулопластика" in low:
            return ("J34.2 Искривление перегородки носа, J31.2 Ронхопатия",
                    "Септопластика, увулопластика")
        if "септо" in low and ("вр" in low or "вазо" in low or "конхобуллез" in low):
            return ("J34.2 Искривление перегородки носа, J30.0 Вазомоторный ринит", "Септопластика, пластика раковин")
        if "септо" in low and "синех" in low:
            return ("J34.2 Искривление перегородки носа, J34.8 Синехии носа", "Септопластика, синехотомия")
        if "септо" in low and ("пазух" in low or "полисинус" in low or "гайморо" in low):
            return ("J34.2 Искривление перегородки носа, J32 Хронический синусит", "Септопластика, гайморотомия")
        if "септо" in low and "киста" in low:
            return ("J34.2 Искривление перегородки носа, J34.0 Киста верхнечелюстной пазухи", "Септопластика, гайморотомия")
        if "септо" in low and "полип" in low:
            return ("J34.2 Искривление перегородки носа, J33 Полип полости носа", "Септопластика, удаление полипа")
        if "септо" in low and "папилома" in low and "миндалины" in low:
            return ("J34.2 Искривление перегородки носа, D14 Образование миндалины", "Септопластика, удаление образования миндалины")
        if "гайморо" in low and ("вазо" in low or "вр" in low):
            return ("J32 Хронический синусит, J30.0 Вазомоторный ринит", "Гайморотомия, пластика раковин")
        if "хрон синусит" in low and ("вр" in low or "вазо" in low):
            return ("J32 Хронический синусит, J30.0 Вазомоторный ринит", "Гайморотомия, пластика раковин")
        if "адено" in low and "+" in diag_raw and "м" in low:
            return ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия")
        if "адено" in low and "м" in low and ("миринг" in low or "отит" in low):
            return ("J35.2 Аденоиды, ГНМ, H65 Хронический средний серозный отит", "Аденотомия, тонзиллотомия, миринготомия")
        if "а+вр" in low or "адено+вр" in low or "ат-вазо" in low or "адено вазо" in low:
            return ("J35.2 Аденоиды, ГНМ, J30.0 Вазомоторный ринит", "Аденотомия, тонзиллотомия, пластика раковин")
        if "вазо" in low and "синехии" in low:
            return ("J30.0 Вазомоторный ринит, J34.8 Синехии носа", "Пластика раковин, синехотомия")

        for key in self.sorted_keys:
            if key.lower() in low:
                return self.diagnosis_map[key]
        if "адено" in low:
            return ("J35.2 Аденоиды, ГНМ", "Аденотомия, тонзиллотомия")
        if "тонзил" in low or "т/э" in low or "т/эктом" in low or "т-э" in low or "тэ" in low:
            return ("J35 Хронический тонзиллит", "Тонзилэктомия")
        if "септо" in low or "септопластика" in low:
            return ("J34.2 Искривление перегородки носа", "Септопластика")
        if "вазо" in low or "вр" in low:
            return ("J30.0 Вазомоторный ринит", "Пластика раковин")
        if "гайморо" in low or "пазух" in low or "синусит" in low:
            return ("J32 Хронический синусит", "Гайморотомия")
        if "атерома" in low or "липома" in low:
            return ("D14 Образование уха", "Удаление образования")
        return (diag_raw if diag_raw else "Диагноз не указан", "Операция не указана")

    def resolve_age_defaults(self, diagnosis_raw: str, current_age: Optional[int]) -> Tuple[int, str]:
        if current_age is not None:
            return current_age, 'г' if current_age >= 18 else 'л'
        if re.search(r'(адено|ат|аден|гнм|тонзил)', diagnosis_raw, re.IGNORECASE):
            return 5, 'л'
        return 44, 'г'

# Глобальный экземпляр
patient_parser = PatientParser()