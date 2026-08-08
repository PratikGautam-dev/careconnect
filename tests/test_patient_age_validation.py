from core.booking_flow import MAX_PATIENT_AGE, MIN_PATIENT_AGE, _parse_patient_age


def test_valid_ages_parsed():
    assert _parse_patient_age("34") == 34
    assert _parse_patient_age("0") == MIN_PATIENT_AGE
    assert _parse_patient_age("120") == MAX_PATIENT_AGE
    assert _parse_patient_age("  7  ") == 7  # surrounding whitespace


def test_non_numeric_rejected():
    assert _parse_patient_age("thirty four") is None
    assert _parse_patient_age("") is None
    assert _parse_patient_age("34.5") is None
    assert _parse_patient_age("-5") is None  # isdigit() rejects the leading '-'


def test_out_of_range_rejected():
    assert _parse_patient_age("121") is None
    assert _parse_patient_age("200") is None
    assert _parse_patient_age("999999999999999999") is None
