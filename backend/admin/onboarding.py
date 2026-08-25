# admin/onboarding.py
"""
Section 15 follow-up: the real onboarding UI is the Next.js wizard
(frontend/src/components/onboarding/OnboardingWizard.tsx, submitting to
admin/onboarding_api.py's JSON endpoint) and the real platform-admin tenant
UI is the Next.js pages under frontend/src/app/admin/ (submitting to
admin/tenants_api.py). This module used to ALSO serve a full parallel
server-rendered HTML wizard and HTML tenant list/edit pages -- genuinely
redundant once the Next.js versions existed, so removed. What's left:

1. Shared validation/parsing helpers still specific to onboarding/tenant-admin
   (_build_departments, _build_faq_topics, _mask_secret, check_admin_secret/
   ADMIN_SECRET, _VALID_TIERS) -- imported directly by admin/onboarding_api.py
   and admin/tenants_api.py, so this module stays even though its own HTML
   routes don't. The genuinely generic field validators used well outside
   admin/ too (_validate_doctor_fields, _parse_offsets) now live in
   admin/validation.py -- _build_departments imports _validate_doctor_fields
   back from there.
2. Two minimal "admin" / "superadmin" entry-point pages (below) -- each just
   a button linking to the real Next.js page, for anyone who still has the
   backend's own URL bookmarked. No forms, no state, nothing to keep in
   sync with the JSON API's own validation.
"""
import hmac

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

import core.rate_limit as rate_limit
from admin.theme import STYLE as _STYLE
from admin.validation import _validate_doctor_fields
from core.config import get_settings

router = APIRouter()

_settings = get_settings()
FRONTEND_ORIGIN = _settings.FRONTEND_ORIGIN

ADMIN_SECRET = _settings.ADMIN_SECRET


def check_admin_secret(secret: str, request: Request) -> bool:
    """Timing-safe (hmac.compare_digest) and rate-limited (audit follow-up,
    Spec.md Section 0) -- shared by every ADMIN_SECRET check in this module
    plus admin/onboarding_api.py's JSON equivalent, so the lockout is one
    counter per caller IP regardless of which of the two entry points
    (HTML wizard vs JSON API) they're hitting."""
    key = rate_limit.client_key("admin_secret", request)
    if rate_limit.is_locked_out(key):
        return False
    ok = bool(ADMIN_SECRET) and hmac.compare_digest(secret or "", ADMIN_SECRET)
    if ok:
        rate_limit.reset(key)
    else:
        rate_limit.record_failure(key)
    return ok

_VALID_TIERS = {"tier1", "tier2", "tier3"}


def _build_departments(
    department_name: list[str],
    doctor_department_index: list[str],
    doctor_name: list[str],
    doctor_specialization: list[str],
    doctor_qualification: list[str],
    doctor_years_experience: list[str],
    doctor_working_days: list[str],
    doctor_working_hours: list[str],
    doctor_slot_duration_minutes: list[str],
    doctor_breaks: list[str] | None = None,
    doctor_max_bookings_per_slot: list[str] | None = None,
    doctor_daily_booking_limit: list[str] | None = None,
    doctor_online_quota: list[str] | None = None,
    doctor_walkin_quota: list[str] | None = None,
    doctor_followup_duration_minutes: list[str] | None = None,
    doctor_effective_from: list[str] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    """Reconstructs department/doctor structures from the wizard's repeatable
    doctor-card fields (Step 7) — parallel arrays positioned in DOM submit
    order, with doctor_department_index[i] naming which department_name[]
    entry doctor i belongs to (recomputed by the page's JS immediately before
    submit, so it always reflects current on-screen card order/removals).
    Returns (departments, errors, warnings) -- Section 14.7's quota-vs-limit
    check is a warning, not an error (see _validate_doctor_fields)."""
    departments = [{"name": n.strip(), "doctors": []} for n in department_name]
    errors: list[str] = []
    warnings: list[str] = []
    doctor_breaks = doctor_breaks or []
    doctor_max_bookings_per_slot = doctor_max_bookings_per_slot or []
    doctor_daily_booking_limit = doctor_daily_booking_limit or []
    doctor_online_quota = doctor_online_quota or []
    doctor_walkin_quota = doctor_walkin_quota or []
    doctor_followup_duration_minutes = doctor_followup_duration_minutes or []
    doctor_effective_from = doctor_effective_from or []

    def _at(lst: list[str], i: int) -> str:
        return lst[i] if i < len(lst) else ""

    for i in range(len(doctor_name)):
        idx_raw = doctor_department_index[i] if i < len(doctor_department_index) else ""
        try:
            dept_idx = int(idx_raw)
        except ValueError:
            errors.append(f"Doctor #{i + 1} is missing a valid department assignment.")
            continue
        if not (0 <= dept_idx < len(departments)):
            errors.append(f"Doctor #{i + 1} references an invalid department.")
            continue

        doctor, doc_errors, doc_warnings = _validate_doctor_fields(
            i,
            doctor_name[i],
            doctor_specialization[i] if i < len(doctor_specialization) else "",
            doctor_qualification[i] if i < len(doctor_qualification) else "",
            doctor_years_experience[i] if i < len(doctor_years_experience) else "",
            doctor_working_days[i] if i < len(doctor_working_days) else "",
            doctor_working_hours[i] if i < len(doctor_working_hours) else "",
            doctor_slot_duration_minutes[i] if i < len(doctor_slot_duration_minutes) else "",
            _at(doctor_breaks, i), _at(doctor_max_bookings_per_slot, i), _at(doctor_daily_booking_limit, i),
            _at(doctor_online_quota, i), _at(doctor_walkin_quota, i),
            _at(doctor_followup_duration_minutes, i), _at(doctor_effective_from, i),
        )
        errors.extend(doc_errors)
        warnings.extend(doc_warnings)
        if doctor is not None:
            departments[dept_idx]["doctors"].append(doctor)

    for i, dept in enumerate(departments):
        if dept["doctors"] and not dept["name"]:
            errors.append(f"Department #{i + 1} has doctors listed but no department name.")

    departments = [d for d in departments if d["name"] and d["doctors"]]
    return departments, errors, warnings


def _build_faq_topics(topic_label: list[str], topic_answer: list[str]) -> tuple[list[dict], list[str]]:
    """Reconstructs topic/answer pairs from the wizard's repeatable topic-card
    fields (Step 8, faq-flow tenants — Section 14.3), mirroring
    _build_departments()'s "skip a card that's entirely empty, error on one
    that's half-filled" shape. Positional pairing (topic_label[i] with
    topic_answer[i]) matches DOM submit order, same as the doctor-card arrays."""
    errors: list[str] = []
    topics: list[dict] = []
    count = max(len(topic_label), len(topic_answer))
    for i in range(count):
        label = (topic_label[i] if i < len(topic_label) else "").strip()
        answer = (topic_answer[i] if i < len(topic_answer) else "").strip()
        if not label and not answer:
            continue  # an untouched "+ Add topic" card -- not an error, just skipped
        if not label:
            errors.append(f"Topic #{i + 1}: label is required (it has an answer but no label).")
            continue
        if not answer:
            errors.append(f'Topic #{i + 1} ("{label}"): answer text is required.')
            continue
        topics.append({"topic_label": label, "answer_text": answer})
    return topics, errors


def _mask_secret(value: str | None) -> str:
    """Same masking rule the Next.js edit-tenant page shows as a hint --
    last 4 characters visible, everything before that replaced with
    bullets. Used by admin/tenants_api.py's tenant-detail response, never
    for the actual credential value."""
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "\u2022\u2022\u2022\u2022"
    return "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" + value[-4:]


def _button_page(eyebrow: str, title: str, description: str, button_label: str, button_href: str) -> str:
    """Shared by both minimal pages below -- a single centered card with one
    button, nothing else. Real functionality (forms, validation, tenant
    data) lives entirely in the Next.js frontend these buttons link to."""
    return f"""<!doctype html>
<html>
<head><title>{title} \u2014 CareConnect</title>{_STYLE}</head>
<body>
<div class="ok-page">
  <div class="brand">
    <div class="brand-mark">H</div>
    <span class="brand-name">{eyebrow}</span>
  </div>
  <h1>{title}</h1>
  <p class="hint">{description}</p>
  <p><a class="btn-secondary" style="background: var(--sage-deep); color: #fff; border: none;" href="{button_href}">{button_label}</a></p>
</div>
</body>
</html>"""


@router.get("/admin/onboard-hospital", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Minimal entry point -- the real guided wizard (Google sign-in +
    ADMIN_SECRET, Section 15) lives at {FRONTEND_ORIGIN}/auth. Ungated:
    there's nothing sensitive on this page, only a link onward to where the
    real gates are enforced."""
    return _button_page(
        "DAAP CareConnect", "Admin", "Onboard a new hospital through the guided setup wizard.",
        "Open onboarding wizard", f"{FRONTEND_ORIGIN}/auth",
    )


@router.get("/admin/tenants", response_class=HTMLResponse)
async def superadmin_page(request: Request):
    """Minimal entry point -- the real tenant list/edit UI (gated by
    TENANTS_ADMIN_SECRET, admin/tenants_api.py) lives at
    {FRONTEND_ORIGIN}/admin/tenants. Ungated here for the same reason as
    admin_page() above -- this page itself shows nothing sensitive."""
    return _button_page(
        "DAAP CareConnect", "Super Admin", "View and edit every onboarded hospital's configuration.",
        "Open tenant admin", f"{FRONTEND_ORIGIN}/admin/tenants",
    )
