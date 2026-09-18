# Geofenced Staff Attendance Check-in/Check-out

Real backend + wiring for the previously frontend-mock `/portal/check-in-out`
and `/portal/attendance` pages: staff check in/out is validated against an
admin-configured hospital location (GPS radius) and/or allowed IP/CIDR
ranges, with shift-aware on-time/late calculation. Configured per hospital
via a new **Settings → Attendance** tab.

## Files changed

### Backend

| File | What changed |
|---|---|
| `backend/db/migrations/versions/20260918090000_add_attendance_geofence_settings.py` | New migration — 9 geofence/shift columns on `hospital_settings` |
| `backend/db/migrations/versions/20260918090100_add_attendance_records.py` | New migration — creates `attendance_records` table |
| `backend/db/migrations/versions/20260918090200_add_attendance_settings_page.py` | New migration — seeds the `attendance_settings` page_key for the Admin role |
| `backend/db/init_db.py` | Mirrored all migrations above (this codebase's test-DB bootstrap is a hand-maintained Python mirror of every migration, not Alembic) |
| `backend/db/orm_models.py` | `HospitalSettings` gains the new columns; new `AttendanceRecord` model |
| `backend/db/repositories/hospital_settings.py` | New getters/defaults + extended `get_hospital_settings()`/`update_hospital_settings()` |
| `backend/db/repositories/attendance.py` | **New** — `check_in()`, `check_out()`, `start_break()`, `end_break()`, `get_today_attendance()`, `get_attendance_history()`, `get_hospital_attendance()`, `auto_checkout_overdue()`; geofence (geopy) + IP/CIDR (stdlib `ipaddress`) verification, hospital-timezone-aware shift on-time/late logic |
| `backend/db/repository.py` | Re-exports `db.repositories.attendance` |
| `backend/portal/routes/attendance.py` | **New** — `/api/portal/attendance/{today,summary,check-in,check-out,break/start,break/end,hospital}` |
| `backend/portal/routes/__init__.py` | Registers the new attendance router |
| `backend/portal/routes/settings.py` | New `GET`/`POST /api/portal/settings/attendance` (separate endpoint from general settings, gated by the `attendance_settings` permission); hoisted `_parse_bounded_int` to module scope (see Bugs section) |
| `backend/portal/permissions.py` | New `PAGE_ATTENDANCE_SETTINGS` page_key (admin-only by default) |
| `backend/pyproject.toml` / `uv.lock` | Added `geopy==2.4.1` dependency |
| `backend/db/migrations/versions/20260919080000_replace_auto_checkout_time_with_grace.py` | New migration — replaces `attendance_auto_checkout_time` ("HH:MM") with `attendance_auto_checkout_grace_minutes` (see Automatic Auto-Checkout below) |
| `backend/webhook/cron_routes.py` | New `POST /internal/auto-checkout` — external-cron-triggered, Redis-locked |
| `backend/core/rate_limit.py` | Extracted shared `client_ip(request)` helper (was duplicated between `attendance.py` and the new `detected_ip` field on Settings → Attendance) |

### Frontend

| File | What changed |
|---|---|
| `frontend/src/hooks/useAttendanceSettings.ts` | **New** — loads/saves the Attendance settings tab; later gained `detected_ip` (read-only) and `attendance_auto_checkout_grace_minutes` |
| `frontend/src/app/portal/settings/_components/AttendanceSettingsTab.tsx` | **New** — hospital location (with "Use my current location"), radius, allowed IP/CIDR list, shift window fields; later gained the "detected IP" box (see Non-technical IP setup below) and the grace-period field |
| `frontend/src/app/portal/settings/_components/SettingsTabsNav.tsx` | Added `"attendance"` to `SettingsTabKey` |
| `frontend/src/app/portal/settings/page.tsx` | Registered the new "Attendance" settings tab |
| `frontend/src/app/portal/check-in-out/page.tsx` | Rewritten to call the real endpoints (geolocation capture on Check In, live status/history from the API); later gained a post-check-in confirmation modal, a friendly status label (was leaking the raw `on_time`/`late` enum), and a proper colored pill for the Quick Actions status line (fixed an invalid `gap-space-1.5` class — this design system's spacing scale only defines whole numbers, so it silently produced zero gap) |
| `frontend/src/app/portal/check-in-out/check-in-out-mock.ts` | Trimmed to just the small display-only constants still used (`HISTORY_STATUS_LABELS/STYLES`, `DEFAULT_REFERENCE_DAY_MINUTES`) |
| `frontend/src/app/portal/attendance/page.tsx` | Rewritten — Present/Late/working-hours/overtime stat tiles, the trend chart, and the records table are now real (fetched from `/api/portal/attendance/summary`); Absent days and the Leave slice stay at 0 (see Known limitation below) |
| `frontend/src/app/portal/attendance/attendance-mock.ts` | Trimmed to just the display constants + month/status filter presets still used |

## Non-technical IP setup (Settings → Attendance)

Whoever configures the Network check doesn't need to read server logs or use
an external "what's my IP" site: the Settings → Attendance page itself shows
"Your current network's IP" (backend: `detected_ip` on `GET /api/portal/
settings/attendance`, via the same `client_ip()` helper the geofence check
itself uses) with an "Add this IP" button. This only works correctly when
whoever's looking at the page is actually on the hospital's real WiFi at
the time — the page says so.

## Automatic Auto-Checkout

`attendance_auto_checkout_grace_minutes` (hospital-wide) + each staff
member's own shift end (`StaffDetail.working_hours`, falling back to the
hospital-wide `attendance_shift_end` when a staff member has none
configured) — replaces an earlier, incorrect design (a single fixed
`"HH:MM"` cutoff) that could not correctly serve two staff on different
shifts at the same hospital (an early cutoff would end a later shift too
soon; a late cutoff would leave an earlier shift's forgotten check-out open
for hours).

**How it's triggered**: this backend has no in-process scheduler — nothing
happens "on its own" without an external trigger, same as the existing
`/internal/send-reminders` etc. `POST /internal/auto-checkout` (secret-gated
via `X-Internal-Secret`, same as those) needs to be hit periodically by an
external cron (a few minutes' interval is reasonable; auto-checkout doesn't
need minute-level precision). One global query (not a per-hospital loop)
finds every still-open `attendance_records` row whose deadline has passed,
computed per-record as: `(that record's date) + (staff's own shift end, or
the hospital's shift end if unset) + (hospital's grace_minutes)`, converted
through the hospital's own timezone. A closed record's `check_out_at` is
set to the deadline moment itself, not whenever the sweep happened to run.

**Safety**: guarded by a short-lived Redis lock (`SET NX EX`, 5 min TTL) so
two overlapping cron triggers don't double-process the same records; the
underlying `UPDATE ... WHERE check_out_at IS NULL` is independently
idempotent even without the lock (e.g. if Redis is unreachable — this
backend treats Redis as optional everywhere, same posture here).

**Example** (grace = 60 min): Staff1 (`11:00-18:00`) → auto-checked-out at
19:00. Staff2 (`15:00-23:30`) → auto-checked-out at 00:30 the next day
(correctly rolls over midnight). Verified directly against the dev database
with exactly this scenario.

**Late-arrival edge case (found and fixed)**: if a staff member checks in
*after* their own `shift_end + grace` has already passed (e.g. shift ends
18:00, grace 60 min → deadline 19:00, but they check in at 19:00 sharp or
later), the very next sweep would otherwise close them out with a
`check_out_at` **before** their own `check_in_at` — a nonsensical record —
within minutes of them arriving, at 0 working minutes. Fixed: the deadline
is now `max(shift_end + grace, check_in_at + grace)`, so a late arrival
still gets a full grace period counted from when they actually checked in,
never a deadline earlier than their own check-in.

**Not yet built**: automatic break start/end (following a staff member's
own scheduled `StaffDetail.breaks` windows) — discussed and designed
(same external-cron + Redis-lock shape as auto-checkout), but not
implemented in this pass. Manual Start Break/End Break remain the only way
to record a break.

## Known limitation: `/portal/attendance`'s Absent/Leave

This feature has no way yet to tell "no check-in row for a day" apart from
"not a working day" or "on approved leave" — that needs cross-referencing a
staff member's configured working days and the existing Leave Requests
table, which is out of scope for this pass. So on `/portal/attendance`:
Present days, Late check-ins, working hours and overtime are all real;
**Absent days always reports 0**, and the Leave slice in the status donut
never appears (since nothing ever writes `status = 'leave'` yet). The
monthly trend chart is a best-effort proxy — % of a week's already-elapsed
days that have a check-in row, not a true "worked / expected" ratio.

## Dependency used

- **`geopy==2.4.1`** (+ its transitive `geographiclib`) — geodesic distance between a staff member's reported GPS position and the hospital's configured location (`geopy.distance.geodesic(...).meters`), used in `db/repositories/attendance.py`. Installed via `uv sync` (already reflected in `uv.lock`).
- Everything else is **already-available stdlib/browser APIs/infrastructure**, added with no new install: Python's `ipaddress` module (IP/CIDR allowlist matching), the browser's native `navigator.geolocation.getCurrentPosition()` (no JS package), and this project's existing Redis connection (`core/redis_client.py`) for the auto-checkout lock.

## How the check works

1. Admin configures **Settings → Attendance**: hospital latitude/longitude + allowed radius (meters), and/or a comma-separated list of allowed IPs/CIDR ranges, plus the shift start/end and early-checkin/late-threshold windows. Every field is optional — leaving geofence + IP both blank disables that check entirely (today's "no gate" behavior is preserved for a hospital that hasn't set this up).
2. On the check-in-out page, "Check In" reads the browser's GPS position (`navigator.geolocation`) and POSTs it, along with the request's own source IP, to `/api/portal/attendance/check-in`.
3. The backend accepts the check-in if **either** configured check passes (GPS within radius, or IP/CIDR match) — a hospital that's only configured one of the two isn't blocked by the other. If neither is configured, it's allowed unconditionally.
4. On a rejection, the error message includes the actual computed distance from the hospital (e.g. "You're 7104m from the hospital (allowed: 150m)") — most real-world rejections during testing turn out to be the device's own location accuracy, not a real mismatch (see Known device-location caveat below), so this makes it self-diagnosable.
5. On-time/late status is computed by converting the check-in's UTC timestamp into the hospital's own local timezone (`hospitals.timezone`) before comparing against the configured shift start — this avoids misjudging lateness for any hospital not on UTC. That shift start is **the staff member's own** (`StaffDetail.working_hours`' earliest start time), falling back to the hospital-wide `attendance_shift_start` only when they have no individual hours configured — the same per-staff-then-fallback resolution auto-checkout uses for shift *end* (see Bugs section: this was originally hospital-wide only, which is wrong the moment two staff at the same hospital work different shifts).
6. On successful Check In, the frontend shows a confirmation modal with the exact time and On Time/Late status.

### Known device-location caveat

A laptop with no GPS chip gets its location from nearby WiFi networks (via a
positioning database) or, failing that, IP-based geolocation. Tethered to a
phone's mobile hotspot, there's usually no known WiFi network to
triangulate against, so the browser falls back to IP geolocation — which
can be off by hundreds of meters to several kilometers. This isn't a bug in
this feature; it showed up during live testing as a geofence rejection that
turned out to be a location-accuracy issue, not a real mismatch. Test from
a phone (real GPS), or use your browser devtools' geolocation override, for
a reliable test.

## Requirements to test this end-to-end

1. **Dependencies installed**: `cd backend && uv sync` (pulls in `geopy`).
2. **Database migrated**: a Postgres instance reachable via `DATABASE_URL` (local `docker compose -f docker-compose.dev-db.yml up -d`, or your dev Neon URL), then:
   ```bash
   cd backend
   export DATABASE_URL=...   # or rely on .env
   uv run alembic upgrade head
   ```
3. **A staff account** logged into the portal, whose role has:
   - `check_in_out` view+write (seeded by default for every non-Admin role — Admin needs it granted manually via Roles & Permissions if that account should self-check-in)
   - `attendance` view to see `/portal/attendance` (same default as above)
   - `attendance_settings` view+write to reach the new Settings → Attendance tab (Admin role only, by default)
4. **Browser geolocation**: the check-in-out page calls `navigator.geolocation.getCurrentPosition()`, which requires either `localhost` or HTTPS, and the browser permission prompt to be accepted. If denied/unavailable, the app still submits the check-in with no coordinates — it will only be accepted if the hospital's IP/CIDR check (or no geofence at all) allows it.
5. **To test geofence rejection**: configure a hospital location + small radius in Settings → Attendance, then use your browser devtools' geolocation override (e.g. Chrome DevTools → Sensors → Location) to simulate a position outside that radius and confirm Check In is rejected with a clear, distance-reporting error.
6. **To test IP allowlisting**: set `attendance_allowed_ip_cidrs` to a CIDR range that does **not** include your current dev machine's IP and confirm rejection (or note that `request.client.host` in local dev is typically `127.0.0.1`, so this is easiest to test against a CIDR you control, e.g. `127.0.0.1/32`, and its inverse).
7. **One check-in/out cycle per calendar day**: once you've checked in today, "Check In" stays locked until you check out (or, for repeated same-day testing, delete that day's row directly from `attendance_records` in the dev DB).
8. **To test auto-checkout**: set `attendance_auto_checkout_grace_minutes` in Settings → Attendance, set a staff member's `working_hours` (or the hospital's own `attendance_shift_end`) to something already in the past, check them in, then `curl -X POST http://localhost:8000/internal/auto-checkout -H "X-Internal-Secret: $INTERNAL_SECRET"` (same secret `.env` already defines for the other `/internal/*` endpoints) — no need to wait for a real external cron during dev. In production, an actual external cron must be configured to hit this endpoint periodically (e.g. every 5 minutes) — nothing runs on its own otherwise.

## Bugs found and fixed during live testing

These surfaced only when actually exercising the running app (not caught by
compile checks or the automated test suite, since nothing in the existing
suite exercises this brand-new feature):

1. **Timezone bug**: on-time/late was computed by comparing a raw UTC
   timestamp against the hospital-local `"HH:MM"` shift start string,
   misjudging lateness for any hospital not on UTC. Fixed by converting the
   check-in moment into the hospital's own `hospitals.timezone` first.
2. **`NameError: _parse_bounded_int`**: it was defined as a nested function
   inside `portal_update_settings()`, so the new `portal_update_attendance_
   settings()` handler couldn't see it — a 500 the first time Settings →
   Attendance was actually saved. Fixed by hoisting it to module scope.
3. **`TypeError: Object of type date is not JSON serializable`**: `_serialize()`
   returned native `datetime.date`/`datetime.datetime` objects, but
   `fastapi.responses.JSONResponse` uses plain `json.dumps()` (not
   `jsonable_encoder`), which can't handle those — a 500 on every real
   check-in/out call. Fixed by converting every timestamp to an ISO string.
4. **Saving General settings silently wiped Attendance settings**:
   `update_hospital_settings()` is a full-object save (every call writes
   every column) — `portal_update_attendance_settings()` correctly read the
   current row first and passed non-attendance fields through unchanged,
   but the pre-existing `portal_update_settings()` (General tab) was never
   updated to do the same for the *new* attendance columns, so every kwarg
   it didn't pass defaulted to `None` and nulled out whatever was saved in
   Settings → Attendance. Fixed the same way: read the current row first,
   pass the 9 attendance fields through unchanged.
5. **On-time/late used the hospital-wide shift start only, ignoring a staff
   member's own shift**: raised by the user asking "if staff has their own
   shift, why do we need the hospital-level shift fields at all?" — which
   surfaced that `_shift_status()` (called from `check_in()`) only ever
   compared against `attendance_shift_start`, never a staff member's own
   `StaffDetail.working_hours`, even though auto-checkout's shift-*end*
   resolution already did exactly that. Two staff on different shifts at
   the same hospital would both be judged late/on-time against one shared
   hospital-wide clock time. Fixed the same way as shift end: staff's own
   working_hours start (earliest start across their ranges), falling back
   to the hospital-wide `attendance_shift_start` only when unset. Verified
   directly: a staff member with a personal `11:00-18:00` shift checking in
   at 11:05 is now `on_time` (was previously ~125 minutes "late" against an
   unrelated hospital-wide `09:00`); the late-by-N-minutes calculation and
   the hospital-wide fallback (for staff with no individual hours) both
   still work correctly.
6. **Auto-checkout could produce `check_out_at` before `check_in_at` for a
   late arrival**: if someone checked in *after* their own `shift_end +
   grace` deadline had already passed, the very next sweep closed them out
   at that already-past deadline — a nonsensical checkout time earlier than
   their check-in, at 0 working minutes, within minutes of arriving. Fixed:
   the deadline is `max(shift_end + grace, check_in_at + grace)`, so a late
   arrival gets a full grace period from their actual check-in instead.

**Takeaway for any future column added to `hospital_settings`**: every
existing caller of `update_hospital_settings()` needs to read-then-pass-
through the new field, not just the caller that owns it — there are
currently two call sites (`portal_update_settings()` and
`portal_update_attendance_settings()`, both in `portal/routes/settings.py`).

## Verification already performed

- `uv run python -m py_compile` on every new/changed backend file.
- `npx tsc --noEmit` across the frontend — no new type errors.
- Ran the real `check_in`/`check_out`/`start_break`/`end_break` flow directly against a live dev Postgres database (geofence acceptance, geofence rejection, double-check-in rejection, break accumulation, hospital roll-up, JSON-serializability of every response) — all behaved as expected after the three bug fixes above, then cleaned up the test data.
- Live end-to-end testing against the running app by the user, surfacing and confirming the fixes for all bugs above.
- Backend test suite: full suite (`uv run pytest -q`, 939 tests) — 938 passed, 1 pre-existing failure unrelated to this feature (`tests/test_booking_flow.py::test_full_happy_path_through_confirmation`, a stale assertion against WhatsApp booking-flow copy that predates this work — nothing in this session touched `flows/` or booking messaging).
- `auto_checkout_overdue()` verified directly against the dev database: per-staff-shift deadline computation (two staff, two different shifts, correct midnight rollover), the opt-in skip (hospital with no grace period configured is never touched), and the hospital-wide `attendance_shift_end` fallback for staff with no individual `working_hours`.
- The Redis lock (`SET NX EX`) verified directly: a second overlapping acquire attempt is correctly blocked, and a fresh acquire succeeds again after release.
- `POST /internal/auto-checkout` verified end-to-end via FastAPI's `TestClient` (in-process, no real server needed): wrong secret → `403`, correct secret → `200` with the real sweep result.
- Re-ran `tests/test_hospital_settings.py`, `tests/test_session_timeout.py`, `tests/test_staff_permission_overrides.py` after the `attendance_auto_checkout_time` → `attendance_auto_checkout_grace_minutes` column replacement (including its `db/init_db.py` mirror) — all still pass.
- Reproduced the late-arrival auto-checkout bug directly (deliberately checking someone in after their own deadline had already passed), confirmed the `check_out_at`-before-`check_in_at` symptom, then re-verified after the fix that the same scenario now correctly waits until `check_in_at + grace` instead.
- Reproduced the on-time/late hospital-wide-only bug directly (staff with a personal `11:00-18:00` shift, hospital-wide `attendance_shift_start` set to an unrelated `09:00`), confirmed it was wrongly marked ~125 minutes late, then re-verified after the fix that the same staff member checking in at 11:05 is correctly `on_time`, a genuinely-late check-in still computes the right `late_minutes`, and the hospital-wide fallback (staff with no individual `working_hours`) is unaffected.
- Re-ran `tests/test_hospital_settings.py`, `tests/test_session_timeout.py`, `tests/test_staff_permission_overrides.py` once more after both fixes — all still pass.
