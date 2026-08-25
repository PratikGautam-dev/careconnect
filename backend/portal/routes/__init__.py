# portal/routes/__init__.py -- mounts one APIRouter per resource
# (auth, dashboard, patients, documents, bookings, doctors, settings,
# handoffs) into a single router app.py includes, mirroring the original
# portal_api.py's flat router but split along resource boundaries.
from fastapi import APIRouter

from portal.routes.auth import router as auth_router
from portal.routes.bookings import router as bookings_router
from portal.routes.dashboard import router as dashboard_router
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
router.include_router(settings_router)
router.include_router(handoffs_router)
