from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, _hospital_summary

router = APIRouter()


@router.get("/api/portal/dashboard")
async def portal_dashboard(authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)

    stats = db.get_dashboard_stats(hospital.id)
    weekly_counts = db.get_weekly_appointment_counts(hospital.id)
    dept_breakdown = db.get_appointments_by_department(hospital.id)
    recent_appointments = db.get_all_appointments_for_hospital(hospital.id, limit=10)
    activity_feed = db.get_recent_activity_feed(hospital.id, limit=10)
    recent_patients = db.get_recent_patients(hospital.id, limit=5)

    return JSONResponse({
        "hospital": _hospital_summary(hospital),
        "stats": stats,
        "weekly_counts": weekly_counts,
        "department_breakdown": dept_breakdown,
        "recent_patients": recent_patients,
        "recent_appointments": [
            {
                "id": a.id,
                "phone": a.phone,
                # Item 3 (Spec.md Section 0): the dashboard's separate "Patients"
                # widget was merged into this table -- patient name now shown
                # inline instead of a second, patient-centric list.
                "patient_name": (db.get_patient_by_phone(hospital.id, a.phone) or {}).get("name"),
                # Patient identity system (Spec.md Section 0): already on the
                # Appointment object itself (via _APPOINTMENT_SELECT's join),
                # no extra query needed the way patient_name above still does.
                "patient_display_id": a.patient_display_id,
                "department_name": a.department_name,
                "doctor_name": a.doctor_name,
                "scheduled_at": a.scheduled_at.isoformat(),
                "status": a.status,
                "source": a.source,
                # Item 9 (Spec.md Section 0): column parity with the full
                # Appointments page, which already surfaces this.
                "reference_id": a.reference_id,
            }
            for a in recent_appointments
        ],
        "activity_feed": [
            {
                "label": item["label"],
                "phone": item["phone"],
                "doctor_name": item["doctor_name"],
                "department_name": item["department_name"],
                "at": item["at"].isoformat(),
            }
            for item in activity_feed
        ],
    })
