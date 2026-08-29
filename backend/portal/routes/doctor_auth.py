# portal/routes/doctor_auth.py
"""Dedicated doctor login (Spec.md Section 0's doctor-portal build) --
issues a doctor-scoped token (auth/doctor_session.py), completely separate
from the shared staff-portal password (portal/routes/auth.py). A doctor's
login is admin-issued (portal/routes/doctors.py's credential route), never
self-registered here."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db.repository as db
from auth.doctor_session import issue_doctor_session
from db.repositories.hospitals import verify_portal_password

router = APIRouter()


class DoctorLoginPayload(BaseModel):
    email: str = ""
    password: str = ""


@router.post("/api/doctor/login")
async def doctor_login(payload: DoctorLoginPayload):
    email = payload.email.strip().lower()
    if not email or not payload.password:
        return JSONResponse({"error": "Email and password are required."}, status_code=400)
    doctor = db.find_doctor_by_email(email)
    # Same shape as the deliberately generic error message
    # find_hospital_by_portal_password()'s caller uses -- never reveals
    # whether the email itself matched a doctor, only whether the whole
    # (email, password) pair is valid.
    if doctor is None or not doctor["password_hash"] or not verify_portal_password(payload.password, doctor["password_hash"]):
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)
    token = issue_doctor_session(doctor["hospital_id"], doctor["id"])
    return JSONResponse({
        "token": token,
        "doctor": {"id": doctor["id"], "name": doctor["name"], "hospital_id": doctor["hospital_id"]},
    })
