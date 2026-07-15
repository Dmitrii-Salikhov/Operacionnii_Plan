"""Тесты нового пайплайна парсера: aliases, combinations, confidence, short keys."""

from patient_parser import (
    PatientParser,
    CONF_COMBINATION,
    CONF_FALLBACK,
    CONF_KEY,
    CONF_UNKNOWN,
    LOW_CONFIDENCE_THRESHOLD,
)


def test_resolve_diagnosis_sources_and_confidence():
    p = PatientParser()
    key = p.resolve_diagnosis("Адено")
    assert key["source"] == "key"
    assert key["confidence"] == CONF_KEY
    assert "Аденотомия" in key["operation"]

    combo = p.resolve_diagnosis("септо вазо")
    assert combo["source"] == "combination"
    assert combo["confidence"] == CONF_COMBINATION
    assert "пластика раковин" in combo["operation"].lower()

    unknown = p.resolve_diagnosis("Совершенно неизвестное")
    assert unknown["source"] == "unknown"
    assert unknown["confidence"] == CONF_UNKNOWN


def test_aliases_normalize_typos_before_matching():
    p = PatientParser()
    # папилома → папиллома, затем комбинация
    r = p.resolve_diagnosis("септо папилома миндалины")
    assert r["source"] == "combination"
    assert "миндалины" in r["diagnosis"].lower() or "образования" in r["operation"].lower()

    # меринго → миринго
    text = p.apply_aliases("ат меринго")
    assert "миринго" in text.lower()


def test_short_key_does_not_match_inside_longer_word():
    p = PatientParser(diagnosis_map={"ат": ("Ат", "Оп"), "атерома": ("Атерома", "Удал")})
    # «ат» не должен цепляться внутри «атерома»
    assert p.find_key_index("атерома мочки", "ат") == -1
    assert p.find_key_index("атерома мочки", "атерома") == 0
    # отдельный токен «ат» находится
    assert p.find_key_index("Иванов ат септо", "ат") >= 0


def test_positional_parse_name_before_diagnosis():
    p = PatientParser()
    patient = p.parse_patient_from_event("Иванов Иван 45 л М/А Септо вазо", "")
    assert patient["name"] == "Иванов Иван"
    assert patient["age"] == 45
    assert patient["is_ma"] is True
    assert "септо" in patient["diagnosis_raw"].lower()


def test_low_confidence_threshold_constant():
    assert CONF_FALLBACK < LOW_CONFIDENCE_THRESHOLD <= CONF_COMBINATION
