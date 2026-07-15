from patient_parser import patient_parser
from gui.unknown_diag_dialog import _unique_diagnosis_options


def test_unique_diagnosis_options_deduplicates_synonym_keys():
    diags, opers = _unique_diagnosis_options()
    assert len(diags) == len(set(diags))
    assert len(opers) == len(set(opers))
    # Много ключей-синонимов → уникальных значений меньше, чем ключей
    assert len(diags) < len(patient_parser.diagnosis_map)
    assert len(opers) < len(patient_parser.diagnosis_map)
