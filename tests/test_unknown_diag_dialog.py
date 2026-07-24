from patient_parser import patient_parser
from gui.unknown_diag_dialog import _needs_review, _review_reason, _unique_diagnosis_options


def test_unique_diagnosis_options_deduplicates_synonym_keys():
    diags, opers = _unique_diagnosis_options()
    assert len(diags) == len(set(diags))
    assert len(opers) == len(set(opers))
    # Много ключей-синонимов → уникальных значений меньше, чем ключей
    assert len(diags) < len(patient_parser.diagnosis_map)
    assert len(opers) < len(patient_parser.diagnosis_map)


def test_short_name_needs_review_flags():
    p = {"needs_name_review": True, "is_unknown_diag": False}
    assert _needs_review(p) is True
    assert "короткое ФИО" in _review_reason(p)
    assert _needs_review({"is_unknown_diag": True}) is True
    assert _needs_review({}) is False
