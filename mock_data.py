# mock_data.py
"""
Hardcoded department/doctor/slot data for the menu-based booking flow (Phase 2).

This is a stand-in for the ERP Integration Layer (SPEC Section 3.4). Phase 3
replaces the functions below with real queries against the hospital ERP
(getDepartments/getDoctors/getAvailableSlots) — everything a patient can pick
from lives in this one file so it's obvious what to swap out.
"""
from datetime import date, timedelta

DEPARTMENTS = [
    {"id": "cardiology", "name": "Cardiology"},
    {"id": "orthopedics", "name": "Orthopedics"},
    {"id": "general_medicine", "name": "General Medicine"},
    {"id": "pediatrics", "name": "Pediatrics"},
]

DOCTORS_BY_DEPARTMENT = {
    "cardiology": [
        {"id": "doc_card_1", "name": "Dr. Anjali Rao"},
        {"id": "doc_card_2", "name": "Dr. Vikram Sethi"},
    ],
    "orthopedics": [
        {"id": "doc_ortho_1", "name": "Dr. Rajesh Kumar"},
        {"id": "doc_ortho_2", "name": "Dr. Meera Nair"},
        {"id": "doc_ortho_3", "name": "Dr. Sanjay Gupta"},
    ],
    "general_medicine": [
        {"id": "doc_gen_1", "name": "Dr. Priya Sharma"},
        {"id": "doc_gen_2", "name": "Dr. Arjun Mehta"},
    ],
    "pediatrics": [
        {"id": "doc_ped_1", "name": "Dr. Kavita Iyer"},
        {"id": "doc_ped_2", "name": "Dr. Rohan Desai"},
        {"id": "doc_ped_3", "name": "Dr. Neha Kapoor"},
    ],
}

_SLOT_TIMES = ("10:00", "15:00")
_SLOT_DAYS_AHEAD = 3


def get_departments() -> list[dict]:
    return DEPARTMENTS


def get_doctors(department_id: str) -> list[dict]:
    return DOCTORS_BY_DEPARTMENT.get(department_id, [])


def get_slots(doctor_id: str) -> list[dict]:
    """
    Next _SLOT_DAYS_AHEAD days, _SLOT_TIMES per day. Same mock list for every
    doctor for now — doctor_id is accepted (not used) so the call shape already
    matches the real getAvailableSlots(doctorId, dateRange) this will become.
    """
    slots = []
    today = date.today()
    for i in range(1, _SLOT_DAYS_AHEAD + 1):
        d = today + timedelta(days=i)
        for t in _SLOT_TIMES:
            slots.append({
                "id": f"{d.isoformat()}_{t}",
                "date": d.isoformat(),
                "time": t,
                "label": f"{d.strftime('%a %d %b')} {t}",
            })
    return slots


def find_department(department_id: str) -> dict | None:
    for d in DEPARTMENTS:
        if d["id"] == department_id:
            return d
    return None


def find_doctor(department_id: str, doctor_id: str) -> dict | None:
    for d in get_doctors(department_id):
        if d["id"] == doctor_id:
            return d
    return None


def find_slot(doctor_id: str, slot_id: str) -> dict | None:
    for s in get_slots(doctor_id):
        if s["id"] == slot_id:
            return s
    return None
