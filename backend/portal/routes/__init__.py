# portal/routes/__init__.py -- mounts one APIRouter per resource
# (auth, dashboard, patients, documents, bookings, doctors, appointment_types,
# settings, handoffs) into a single router app.py includes, mirroring the
# original portal_api.py's flat router but split along resource boundaries.
from fastapi import APIRouter

from portal.routes.appointment_types import router as appointment_types_router
from portal.routes.auth import router as auth_router
from portal.routes.bookings import router as bookings_router
from portal.routes.dashboard import router as dashboard_router
from portal.routes.daycare_duration_options import router as daycare_duration_options_router
from portal.routes.doctor_auth import router as doctor_auth_router
from portal.routes.doctor_portal import router as doctor_portal_router
from portal.routes.doctors import router as doctors_router
from portal.routes.documents import router as documents_router
from portal.routes.handoffs import router as handoffs_router
from portal.routes.patients import router as patients_router
from portal.routes.settings import router as settings_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(patients_router)
router.include_router(documents_router)
router.include_router(bookings_router)
router.include_router(doctors_router)
router.include_router(appointment_types_router)
router.include_router(daycare_duration_options_router)
router.include_router(settings_router)
router.include_router(handoffs_router)
# Dedicated doctor login (Spec.md Section 0's doctor-portal build) -- a
# separate /api/doctor/* surface, not /api/portal/*, gated by its own
# doctor-scoped token (auth/doctor_session.py), never the shared staff
# portal's hospital-wide one.
router.include_router(doctor_auth_router)
router.include_router(doctor_portal_router)
