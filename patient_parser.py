import re
import json
import os
import sys
from datetime import datetime
from collections import Counter
from typing import Optional, Tuple, Dict, Any, List

DEFAULT_DIAGNOSES_FILE = "diagnoses.json"
DEFAULT_COMBINATIONS_FILE = "diagnosis_combinations.json"
DEFAULT_ALIASES_FILE = "diagnosis_aliases.json"

# Ключи длиной ≤ SHORT_KEY_MAX_LEN матчатся только как отдельные токены
SHORT_KEY_MAX_LEN = 4

# Уровни уверенности
CONF_KEY = 1.0
CONF_COMBINATION = 0.9
CONF_FALLBACK = 0.55
CONF_UNKNOWN = 0.0
LOW_CONFIDENCE_THRESHOLD = 0.75


def _resolve_resource_path(filename: str) -> str:
    """Ищет файл рядом со скриптом, в _MEIPASS (PyInstaller) или в cwd."""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, filename))
        candidates.append(os.path.join(os.path.dirname(sys.executable), filename))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, filename))
    candidates.append(os.path.join(os.getcwd(), filename))
    candidates.append(filename)
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def load_diagnosis_map_from_json(path: str) -> Dict[str, Tuple[str, str]]:
    """Загружает словарь ключ → (диагноз, операция) из JSON."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    result: Dict[str, Tuple[str, str]] = {}
    for key, value in raw.items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            result[key] = (str(value[0]), str(value[1]))
        else:
            raise ValueError(f"Неверный формат диагноза для ключа '{key}'")
    return result


def load_combinations_from_json(path: str) -> List[Dict[str, Any]]:
    """Загружает правила комбинаций: [{pattern, diagnosis, operation}, ...]."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("combinations", raw) if isinstance(raw, dict) else raw
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        pattern = item.get("pattern")
        diagnosis = item.get("diagnosis")
        operation = item.get("operation")
        if pattern and diagnosis and operation:
            result.append({
                "pattern": str(pattern),
                "diagnosis": str(diagnosis),
                "operation": str(operation),
                "regex": re.compile(str(pattern), re.IGNORECASE),
            })
    return result


def load_aliases_from_json(path: str) -> Dict[str, str]:
    """Загружает словарь опечаток: неправильно → правильно."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        return {}
    return {str(k).lower(): str(v).lower() for k, v in raw.items()}


class PatientParser:
    def __init__(
        self,
        diagnosis_map: Optional[Dict[str, Tuple[str, str]]] = None,
        custom_diag_file: str = "custom_diagnoses.json",
        diagnoses_file: str = DEFAULT_DIAGNOSES_FILE,
        combinations_file: str = DEFAULT_COMBINATIONS_FILE,
        aliases_file: str = DEFAULT_ALIASES_FILE,
    ):
        if diagnosis_map is not None:
            self.diagnosis_map = dict(diagnosis_map)
        else:
            path = _resolve_resource_path(diagnoses_file)
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Не найден словарь диагнозов '{diagnoses_file}'. "
                    f"Ожидался файл: {path}"
                )
            self.diagnosis_map = load_diagnosis_map_from_json(path)

        self.custom_diag_file = custom_diag_file
        self.load_custom_diagnoses()
        self.sort_keys()

        combo_path = _resolve_resource_path(combinations_file)
        self.combinations = load_combinations_from_json(combo_path)

        alias_path = _resolve_resource_path(aliases_file)
        self.aliases = load_aliases_from_json(alias_path)

    def load_custom_diagnoses(self):
        if os.path.exists(self.custom_diag_file):
            with open(self.custom_diag_file, "r", encoding="utf-8") as f:
                custom = json.load(f)
            for key, value in custom.items():
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    self.diagnosis_map[key] = (str(value[0]), str(value[1]))

    def save_custom_diagnosis(self, key: str, diag: str, operation: str):
        custom = {}
        if os.path.exists(self.custom_diag_file):
            with open(self.custom_diag_file, "r", encoding="utf-8") as f:
                custom = json.load(f)
        custom[key] = [diag, operation]
        with open(self.custom_diag_file, "w", encoding="utf-8") as f:
            json.dump(custom, f, ensure_ascii=False, indent=2)
        self.diagnosis_map[key] = (diag, operation)
        self.sort_keys()

    def save_custom_diagnoses_full(self):
        with open(self.custom_diag_file, "w", encoding="utf-8") as f:
            payload = {k: list(v) for k, v in self.diagnosis_map.items()}
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def sort_keys(self):
        self.sorted_keys = sorted(
            self.diagnosis_map.keys(), key=lambda k: len(k), reverse=True
        )

    # ---------- Нормализация / безопасный матч ----------
    def apply_aliases(self, text: str) -> str:
        """Заменяет известные опечатки на канонические формы."""
        if not text or not self.aliases:
            return text
        result = text
        # Длинные алиасы раньше коротких
        for wrong in sorted(self.aliases.keys(), key=len, reverse=True):
            right = self.aliases[wrong]
            if wrong == right:
                continue
            result = re.sub(
                re.escape(wrong), right, result, flags=re.IGNORECASE
            )
        return result

    @staticmethod
    def _needs_token_boundary(key: str) -> bool:
        """Короткие ключи и аббревиатуры — только как отдельные токены."""
        return len(key) <= SHORT_KEY_MAX_LEN

    def find_key_index(self, text: str, key: str) -> int:
        """Индекс первого вхождения ключа (−1 если нет). Короткие — по границам."""
        if not text or not key:
            return -1
        low = text.lower()
        k = key.lower()
        if self._needs_token_boundary(key):
            pattern = (
                r"(?<![а-яёa-z0-9])"
                + re.escape(k)
                + r"(?![а-яёa-z0-9])"
            )
            match = re.search(pattern, low, re.IGNORECASE)
            return match.start() if match else -1
        return low.find(k)

    def find_earliest_diagnosis_key(self, text: str) -> Tuple[Optional[str], int]:
        """Самый левый ключ диагноза в тексте (длинные приоритетнее при равном индексе)."""
        best_key = None
        best_idx = len(text) + 1
        for key in self.sorted_keys:
            idx = self.find_key_index(text, key)
            if idx == -1:
                continue
            if idx < best_idx or (idx == best_idx and best_key is not None and len(key) > len(best_key)):
                best_idx = idx
                best_key = key
        if best_key is None:
            return None, -1
        return best_key, best_idx

    # ---------- Методы извлечения ----------
    def extract_age_and_clean(self, text: str) -> Tuple[Optional[int], Optional[str], str]:
        m_date = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if m_date:
            day, month, year = map(int, m_date.groups())
            try:
                birth_date = datetime(year, month, day)
                today = datetime.now()
                age = today.year - birth_date.year - (
                    (today.month, today.day) < (birth_date.month, birth_date.day)
                )
                clean = text[: m_date.start()] + text[m_date.end() :]
                clean = re.sub(r"\s*г\.?\s*р?\.?\s*$", "", clean).strip()
                return age, "л", clean
            except ValueError:
                pass

        m = re.search(
            r"(\d+)\s*(л|лет|год|года|г)\.?(?=\s|$)", text, re.IGNORECASE
        )
        if m:
            num = int(m.group(1))
            unit_raw = m.group(2).lower()
            unit = "л" if "л" in unit_raw else "г"
            if num > 120:
                birth_year = num
                today = datetime.now()
                age = today.year - birth_year
                clean = text[: m.start()] + text[m.end() :]
                clean = re.sub(r"\s*г\.?\s*$", "", clean).strip()
                return age, "л", clean
            clean = text[: m.start()] + text[m.end() :]
            clean = re.sub(r"\s\.\s", " ", clean).strip()
            clean = re.sub(r"^\s*\.\s*", "", clean).strip()
            return num, unit, clean.strip()

        m = re.search(r"(\d{4})\s*г\.?\s*р?\.?", text, re.IGNORECASE)
        if m:
            birth_year = int(m.group(1))
            today = datetime.now()
            age = today.year - birth_year
            clean = text[: m.start()] + text[m.end() :]
            return age, "л", clean.strip()

        DIAG_TERMS = [
            "тонз", "т/э", "т/эктом", "септо", "адено", "ат", "гнм", "миринго",
            "вазо", "вр", "полип", "гайморо", "решетки", "синехии", "атерома",
            "липома", "увуло", "папиллома", "перфорация", "полисинусо", "хрон", "киста",
        ]
        pattern = r"(\d+)\s+(?=(?:" + "|".join(DIAG_TERMS) + r")\b)"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            clean = text[: m.start()] + text[m.end() :]
            return age, "л", clean.strip()
        return None, None, text

    def extract_anesthesia_markers(self, text: str) -> Tuple[bool, bool, str]:
        """Выделяет М/А и ЭТН, убирает маркеры из текста."""
        is_ma = bool(re.search(r"\b[Мм]/[Аа]\b", text))
        is_etn = bool(re.search(r"\bЭТН\b", text, re.IGNORECASE))
        clean = re.sub(r"\b[Мм]/[Аа]\b", " ", text)
        clean = re.sub(r"\bЭТН\b", " ", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not is_ma and not is_etn:
            is_etn = True
        return is_ma, is_etn, clean

    def normalize_name(self, raw_name: str) -> str:
        if not raw_name:
            return raw_name
        name = re.sub(r"[^а-яёА-ЯЁa-zA-Z\. ]", " ", raw_name)
        name = re.sub(r"\s+", " ", name).strip()
        parts = name.split()
        out = []
        for p in parts:
            if re.fullmatch(r"г\.?р?\.?", p, re.IGNORECASE):
                continue
            if re.fullmatch(r"г\.?", p, re.IGNORECASE):
                continue
            if re.match(r"^[а-яёa-z]\.?[а-яёa-z]?\.?$", p, re.IGNORECASE):
                out.append(p.upper().replace(".", ".") if "." in p else p.upper() + ".")
            else:
                out.append(p.capitalize())
        return " ".join(out)

    def get_surname_and_initials(self, full_name: str) -> Tuple[str, str]:
        parts = full_name.split()
        if not parts:
            return "", ""
        surname = parts[0]
        initials = []
        for part in parts[1:]:
            if re.match(r"^[А-ЯЁA-Z]\.[А-ЯЁA-Z]?\.?$", part):
                initials.append(part.rstrip("."))
            elif len(part) > 1 and not re.match(r"^[А-ЯЁA-Z]\.", part):
                initials.append(part[0].upper())
        initials_str = ".".join(initials) + "." if initials else ""
        return surname, initials_str

    def build_display_name(self, full_name: str, surname_counter: Counter) -> str:
        surname, initials = self.get_surname_and_initials(full_name)
        if surname_counter[surname] > 1 and initials:
            return f"{surname} {initials}"
        return surname

    def clean_phone_numbers(self, text: str) -> str:
        text = re.sub(
            r"\+?\d{1,3}\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}", " ", text
        )
        text = re.sub(r"[78]\d{10}", " ", text)
        return text

    def sanitize_text(self, text: str) -> str:
        text = re.sub(r"[\u00A0\u200B-\u200F\u2028-\u202F\uFEFF]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _unwrap_brackets_with_diag(self, text: str) -> str:
        """Скобки с ключом диагноза раскрываем, остальные убираем."""

        def repl(match):
            content = match.group(1)
            for k in self.diagnosis_map:
                if self.find_key_index(content, k) != -1:
                    return " " + content + " "
            return " "

        return re.sub(r"\(([^)]+)\)", repl, text)

    def parse_patient_from_event(
        self, title: str, description: str, logger=None
    ) -> Optional[Dict[str, Any]]:
        """
        Позиционный разбор: ФИО [возраст] [М/А|ЭТН] диагноз...
        Имя — всё до первого ключа диагноза.
        """
        title = str(title).replace("nan", "") if title else ""
        description = str(description).replace("nan", "") if description else ""
        full_text = f"{title} {description}".strip()
        if logger:
            logger(f"[ИСХОДНАЯ] {full_text}")

        full_text = self.sanitize_text(full_text)
        full_text = self.clean_phone_numbers(full_text)
        full_text = self.apply_aliases(full_text)
        clean = re.sub(r"\s+", " ", full_text).strip()
        if logger:
            logger(f"[БЕЗ ТЕЛЕФОНОВ/АЛИАСЫ] {clean}")
        if not clean:
            return None

        has_osteotomy = bool(re.search(r"остеотоми[яи]", clean, re.IGNORECASE))
        is_ma, is_etn, clean = self.extract_anesthesia_markers(clean)

        age, unit, clean = self.extract_age_and_clean(clean)
        if logger:
            logger(f"[ПОСЛЕ ИЗВЛ. ВОЗРАСТА] age={age}, unit={unit}, clean='{clean}'")

        clean = re.sub(r"\bг\.?\b", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return None

        # Раскрыть скобки с диагнозом, затем искать ключ
        search_text = self._unwrap_brackets_with_diag(clean)
        search_text = re.sub(r"\s+", " ", search_text).strip()
        best_key, best_idx = self.find_earliest_diagnosis_key(search_text)

        is_unknown_diag = False
        if best_key is None:
            name_part = re.sub(r"\(.*?\)", "", clean).strip()
            diag_part = ""
            is_unknown_diag = True
        else:
            # Имя — до ключа в search_text; диагноз — от ключа
            name_part = search_text[:best_idx].strip()
            diag_part = search_text[best_idx:].strip()

        if logger:
            logger(f"[ИМЯ/ДИАГНОЗ] name_part='{name_part}', diag_part='{diag_part}'")

        name_part = re.sub(r"\(.*?\)", "", name_part)
        name_part = name_part.replace("...", "").replace("…", "")
        name_part = name_part.strip(". ")
        patient_name = self.normalize_name(name_part)
        if logger:
            logger(f"[ПОСЛЕ normalize_name] '{patient_name}'")

        if len(patient_name.replace(".", "").strip()) <= 2:
            if logger:
                logger(f"[ИГНОРИРОВАНО] Имя слишком короткое: '{patient_name}'")
            return None

        diag_part_clean = re.sub(r"[?]+", "", diag_part).strip()
        diag_part_clean = re.sub(
            r"\bбулла\b", "", diag_part_clean, flags=re.IGNORECASE
        ).strip()
        diag_part_clean = re.sub(r"\s+", " ", diag_part_clean).strip()
        if not diag_part_clean and not is_unknown_diag:
            return None

        if logger:
            logger(
                f"[ФИНАЛ] name='{patient_name}', age={age}, "
                f"diag_raw='{diag_part_clean}'\n"
            )

        return {
            "name": patient_name,
            "age": age,
            "age_unit": unit if unit else ("г" if age and 1 <= age <= 4 else "л"),
            "diagnosis_raw": diag_part_clean,
            "is_ma": is_ma,
            "is_etn": is_etn,
            "has_osteotomy": has_osteotomy,
            "is_unknown_diag": is_unknown_diag,
            "confidence": CONF_UNKNOWN if is_unknown_diag else None,
            "phones": [],
            "full_text": full_text,
        }

    def resolve_diagnosis(self, diag_raw: str) -> Dict[str, Any]:
        """
        Единый пайплайн: алиасы → комбинации (JSON) → ключ словаря → fallback.
        Возвращает diagnosis, operation, confidence, source.
        """
        raw = (diag_raw or "").strip()
        normalized = self.apply_aliases(raw)
        low = normalized.lower()

        # 1) Комбинации из JSON (порядок = приоритет)
        for combo in self.combinations:
            if combo["regex"].search(low):
                return {
                    "diagnosis": combo["diagnosis"],
                    "operation": combo["operation"],
                    "confidence": CONF_COMBINATION,
                    "source": "combination",
                }

        # 2) Точное вхождение ключа словаря (длинные раньше)
        for key in self.sorted_keys:
            if self.find_key_index(normalized, key) != -1:
                diag, oper = self.diagnosis_map[key]
                return {
                    "diagnosis": diag,
                    "operation": oper,
                    "confidence": CONF_KEY,
                    "source": "key",
                }

        # 3) Эвристический fallback — низкая уверенность
        if "адено" in low:
            return {
                "diagnosis": "J35.2 Аденоиды, ГНМ",
                "operation": "Аденотомия, тонзиллотомия",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }
        if (
            "тонзил" in low
            or "т/э" in low
            or "т/эктом" in low
            or "т-э" in low
            or re.search(r"(?<![а-яёa-z0-9])тэ(?![а-яёa-z0-9])", low)
        ):
            return {
                "diagnosis": "J35 Хронический тонзиллит",
                "operation": "Тонзилэктомия",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }
        if "септо" in low or "септопластика" in low:
            return {
                "diagnosis": "J34.2 Искривление перегородки носа",
                "operation": "Септопластика",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }
        if "вазо" in low or re.search(r"(?<![а-яёa-z0-9])вр(?![а-яёa-z0-9])", low):
            return {
                "diagnosis": "J30.0 Вазомоторный ринит",
                "operation": "Пластика раковин",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }
        if "гайморо" in low or "пазух" in low or "синусит" in low:
            return {
                "diagnosis": "J32 Хронический синусит",
                "operation": "Гайморотомия",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }
        if "атерома" in low or "липома" in low:
            return {
                "diagnosis": "D14 Образование уха",
                "operation": "Удаление образования",
                "confidence": CONF_FALLBACK,
                "source": "fallback",
            }

        return {
            "diagnosis": raw if raw else "Диагноз не указан",
            "operation": "Операция не указана",
            "confidence": CONF_UNKNOWN,
            "source": "unknown",
        }

    def get_diagnosis_and_operation(self, diag_raw: str) -> Tuple[str, str]:
        """Совместимость: (диагноз, операция)."""
        result = self.resolve_diagnosis(diag_raw)
        return result["diagnosis"], result["operation"]

    def resolve_age_defaults(
        self, diagnosis_raw: str, current_age: Optional[int]
    ) -> Tuple[int, str]:
        if current_age is not None:
            return current_age, "г" if current_age >= 18 else "л"
        if re.search(r"(адено|ат|аден|гнм|тонзил)", diagnosis_raw, re.IGNORECASE):
            return 5, "л"
        return 44, "г"


# Глобальный экземпляр
patient_parser = PatientParser()
