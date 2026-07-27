from datetime import date, timedelta

import mock_data


def test_get_departments_returns_four_fixed_departments():
    depts = mock_data.get_departments()
    ids = {d["id"] for d in depts}
    assert ids == {"cardiology", "orthopedics", "general_medicine", "pediatrics"}


def test_get_doctors_returns_two_or_three_per_department():
    for dept in mock_data.get_departments():
        doctors = mock_data.get_doctors(dept["id"])
        assert 2 <= len(doctors) <= 3
        assert all("id" in d and "name" in d for d in doctors)


def test_get_doctors_unknown_department_returns_empty():
    assert mock_data.get_doctors("nonexistent") == []


def test_get_slots_returns_next_three_days_two_per_day():
    slots = mock_data.get_slots("doc_card_1")
    assert len(slots) == 6
    expected_dates = {(date.today() + timedelta(days=i)).isoformat() for i in (1, 2, 3)}
    assert {s["date"] for s in slots} == expected_dates
    for d in expected_dates:
        times = {s["time"] for s in slots if s["date"] == d}
        assert times == {"10:00", "15:00"}


def test_find_department_found_and_not_found():
    assert mock_data.find_department("cardiology")["name"] == "Cardiology"
    assert mock_data.find_department("nope") is None


def test_find_doctor_found_and_not_found():
    doctors = mock_data.get_doctors("cardiology")
    doctor = mock_data.find_doctor("cardiology", doctors[0]["id"])
    assert doctor == doctors[0]
    assert mock_data.find_doctor("cardiology", "nope") is None
    assert mock_data.find_doctor("nope", doctors[0]["id"]) is None


def test_find_slot_found_and_not_found():
    slots = mock_data.get_slots("doc_card_1")
    slot = mock_data.find_slot("doc_card_1", slots[0]["id"])
    assert slot == slots[0]
    assert mock_data.find_slot("doc_card_1", "nope") is None
