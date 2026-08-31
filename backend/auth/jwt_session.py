# auth/jwt_session.py
"""RBAC staff/super-admin access tokens (docs/rbac-redis-plan.md) -- PyJWT
instead of this codebase's existing custom HMAC "field.field....sig" scheme
(auth/session.py, auth/doctor_session.py) because a JWT lets the frontend
(and any future service) inspect hospital_id/role client-side without a
round-trip, using standard tooling instead of a bespoke parser, while still
being exactly as revocable in practice: `tv` (token_version) is checked
against the live DB value on every request (portal/deps.py's
get_current_staff()), so a stolen/leaked token dies the moment an admin
bumps it (password change/deactivation/role change), same as the HMAC
scheme's own "short TTL, re-issued not extended" posture -- just with an
immediate kill switch added on top, which the plain-HMAC scheme never had.

Two structurally separate token types, same "a leaked secret should only
forge the one thing it's for" precedent DOCTOR_SECRET vs PORTAL_SECRET
already established: `typ: "staff"` tokens are signed with JWT_SECRET,
`typ: "super_admin"` tokens with SUPER_ADMIN_JWT_SECRET -- verify_access_token()
checks `typ` explicitly (not just signature validity) so even a token signed
with the WRONG secret by coincidence (impossible in practice, but the check
costs nothing) or a future third token type can never be silently accepted
by the wrong verifier.

15-minute TTL (deliberately short, unlike auth/session.py's 24h) -- this is
what makes token_version-based revocation feel close to immediate rather
than "immediate, but only after today's still-24h-old token would have
expired anyway": the refresh-token dance (auth/refresh_tokens.py) exists
specifically so a 15-minute access-token lifetime doesn't mean logging every
staff member out every 15 minutes."""
import time

import jwt

from core.config import get_settings

_ACCESS_TOKEN_TTL_SECONDS = 15 * 60


def _secret_for(typ: str) -> str:
    settings = get_settings()
    return settings.SUPER_ADMIN_JWT_SECRET if typ == "super_admin" else settings.JWT_SECRET


def issue_access_token(
    subject_id: int, hospital_id: int | None, role: str, token_version: int, typ: str = "staff",
) -> str:
    """hospital_id is None only for a super_admin token (typ="super_admin") --
    a super admin has no hospital scope at all (super_admins is a global
    table, db/orm_models.py's own docstring). `sub` is the staff_users.id or
    super_admins.id, never doctors.id/hospitals.id, so a caller reading this
    claim always knows unambiguously which table it resolves against based
    on `typ` alone."""
    now = int(time.time())
    payload = {
        "sub": subject_id,
        "hospital_id": hospital_id,
        "role": role,
        "tv": token_version,
        "iat": now,
        "exp": now + _ACCESS_TOKEN_TTL_SECONDS,
        "typ": typ,
    }
    return jwt.encode(payload, _secret_for(typ), algorithm="HS256")


def verify_access_token(token: str, expected_typ: str = "staff") -> dict | None:
    """Returns the decoded claims dict if `token` is a validly-signed,
    unexpired, expected_typ-matching JWT, else None -- PyJWT itself raises on
    a bad signature/expired exp, so every failure mode collapses to the same
    None a caller treats as "not authenticated", matching every other
    verify_*() function in this codebase's auth/ package (never raises,
    always returns None on any failure)."""
    try:
        claims = jwt.decode(token, _secret_for(expected_typ), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != expected_typ:
        return None
    return claims
