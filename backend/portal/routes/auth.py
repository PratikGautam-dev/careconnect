# portal/routes/auth.py
"""
JSON API for the Next.js hospital-staff portal (frontend/src/app/portal) --
auth/session.py is the original server-rendered HTML portal's session
signing/verification, reused here rather than re-implemented; this module
just exposes the login operation as JSON.

Transport differs deliberately: a cookie is fine for a same-origin
server-rendered page, but the Next.js frontend runs on a different
origin/port (localhost:3000 vs this API's localhost:8000, a real
cross-site relationship even in dev) where a third-party cookie needs
SameSite=None + Secure -- not viable over plain http in local dev. Instead
the signed "hospital_id.expires_epoch.signature" token auth/session.py
already generates (_sign_session) is returned in the JSON body and sent back
by the frontend as a Bearer token, verified with the exact same
_verify_session -- same signature, same TTL, same "basic protection"
posture, just a different transport.
"""
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import core.rate_limit as rate_limit
import db.repository as db
from auth.session import _SESSION_TTL_SECONDS, _sign_session
from portal.deps import _hospital_summary

router = APIRouter()


@router.post("/api/portal/login")
async def portal_login(payload: dict, request: Request):
    key = rate_limit.client_key("portal_login", request)
    if rate_limit.is_locked_out(key):
        return JSONResponse(
            {"error": "Too many attempts. Please wait a while before trying again."}, status_code=429
        )

    password = (payload or {}).get("password", "")
    hospital = db.find_hospital_by_portal_password(password) if password else None
    if hospital is None:
        rate_limit.record_failure(key)
        return JSONResponse({"error": "Incorrect password."}, status_code=403)

    rate_limit.reset(key)
    expires_at = int(time.time()) + _SESSION_TTL_SECONDS
    token = _sign_session(hospital.id, expires_at)
    return JSONResponse({"token": token, "expires_at": expires_at, "hospital": _hospital_summary(hospital)})
