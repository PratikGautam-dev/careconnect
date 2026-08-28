# Per-appointment-type booking flow (Phase 1: structure, Phase 2: behavior)

## Context

Appointment type selection already exists (`appointment_types` table, `STATE_AWAITING_APPOINTMENT_TYPE`,
7 default types: new, followup, tele, second_opinion, diagnostic, lab, daycare — each with
`requires_consent`/`requires_doctor_selection` flags). But after the user picks a type, every type
funnels through the *identical* hardcoded pipeline: department → doctor → date → time-slot →
confirm → (consent) → create. `requires_doctor_selection` is stored and seeded but never read
anywhere in `flows/booking/*.py` — confirmed via `grep -rn "requires_doctor_selection"`, only
hits are DB/repo/seed code and one test fixture. So diagnostic/lab still force a department+doctor
pick today even though nothing about them needs one.

This isn't sustainable: as more type-specific rules get added (daycare date-ranges, tele video
links, lab test selection, etc.), that logic would have to get jammed into the same shared
handler functions as more and more `if appointment_type_id == "..."` branches, making
`flows/booking/book.py` unreadable. The user wants each type's flow kept **separately** so the
code structure mirrors the business concept — while still not duplicating the shared mechanics
(patient resolution, confirmation, consent gate, resource-locked creation) that every type
actually shares.

**Confirmed with user**: this pass is Phase 1 — pure restructuring — with one concrete Phase-1
behavior change: diagnostic/lab skip department AND doctor selection entirely, going straight
from appointment-type selection to date/time-slot. Every other type (new, followup, tele,
second_opinion, daycare) keeps today's exact department→doctor→date→slot→confirm(→consent)
sequence, unchanged, in this pass. Phase 2 (later, separate pass) is where further per-type
divergence lands (e.g. daycare date-range instead of single slot, tele video-link generation,
lab/diagnostic test-selection step) — the structure built in Phase 1 is what makes Phase 2 additions
land as new files instead of new branches in shared code.

## Design: per-type "step list" strategy, not per-type flow duplication

Rather than writing 7 fully separate state machines (duplicating the department/doctor/date/slot
handler bodies 7 times), each appointment type gets an ordered **step list** — the sequence of
shared states it passes through — and the existing generic handlers (department picker, doctor
picker, date picker, slot picker — unchanged bodies) become step-list-driven instead of
hardcoded-next-state. This is the standard way to give each type "its own flow" for readability
and future divergence, without duplicating mechanics that are genuinely identical today.

### New package: `backend/flows/booking/types/`

- **`base.py`** — `TypeFlow` dataclass: `type_id: str`, `steps: tuple[str, ...]` (ordered
  subset of `STATE_AWAITING_DEPARTMENT` / `_DOCTOR` / `_DATE` / `_TIME_SLOT` /
  `STATE_AWAITING_CONFIRMATION`, always ending in `STATE_AWAITING_CONFIRMATION`). Methods:
  `first_step()`, `next_step(current) -> str | None`, `prev_step(current) -> str | None`
  (walks the tuple; "before first step" resolves back to `STATE_AWAITING_APPOINTMENT_TYPE`).
- **Two shared step-list constants** (in `base.py`, reused by multiple type modules —
  not duplicated per file):
  ```python
  FULL_FLOW = (STATE_AWAITING_DEPARTMENT, STATE_AWAITING_DOCTOR, STATE_AWAITING_DATE,
               STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION)
  NO_DOCTOR_FLOW = (STATE_AWAITING_DATE, STATE_AWAITING_TIME_SLOT, STATE_AWAITING_CONFIRMATION)
  ```
- **One small module per type** (this is the literal "keep type flow separate" ask — each file
  is where that type's future custom behavior will live, even though today most just declare
  which shared step list they use):
  - `new_consultation.py`, `followup.py`, `tele_consultation.py`, `second_opinion.py`,
    `daycare.py` → each: `FLOW = TypeFlow(type_id="...", steps=FULL_FLOW)`.
  - `diagnostic.py`, `lab.py` → each: `FLOW = TypeFlow(type_id="...", steps=NO_DOCTOR_FLOW)`
    — this is the one real Phase-1 behavior change.
- **`registry.py`** — `TYPE_FLOWS: dict[str, TypeFlow]` built from the modules above;
  `get_type_flow(appointment_type_id: str) -> TypeFlow` returns the match or a `FULL_FLOW`
  default for any hospital-custom type id not in the built-in catalog (so a hospital adding a
  novel type later doesn't crash the flow — it just gets the full generic pipeline until someone
  gives it its own module).

### Changes to existing files (mechanics stay generic, only *transitions* become data-driven)

- **`flows/booking/book.py`**:
  - `_handle_awaiting_appointment_type`: after storing `appointment_type_id` in context, replace
    the hardcoded `→ STATE_AWAITING_DEPARTMENT` transition with
    `get_type_flow(appointment_type_id).first_step()`.
  - Department/doctor/date/time-slot completion branches: replace each hardcoded "next state"
    constant with `get_type_flow(context["appointment_type_id"]).next_step(current_state)`.
  - Back-navigation (`_CHANGE_TARGETS`, and wherever `_history_pop_to`/`_find_by_id` walk
    backwards) uses `flow.prev_step(current_state)` instead of the static dict, so diagnostic/lab
    back-navigate from DATE straight to APPOINTMENT_TYPE (no department/doctor to return to).
  - `_handle_awaiting_confirmation`'s existing consent gate
    (`if context.get("appointment_type_requires_consent"): → STATE_AWAITING_CONSENT`) is
    untouched — consent stays a DB-driven flag orthogonal to the step-list, not part of `steps`.
- **`flows/booking/messages.py`**: the "Change ..." selection menu (`_send_change_selection` /
  equivalent) builds its options from `flow.steps` instead of a fixed list, so diagnostic/lab
  only ever show "Change Date" / "Change Time", never "Change Department" / "Change Doctor".
- **`flows/booking/state.py`**: no new states needed — `STATE_AWAITING_DEPARTMENT`/`_DOCTOR` are
  simply absent from `NO_DOCTOR_FLOW`'s step tuple, so their handlers are never entered for
  diagnostic/lab; their handler bodies stay completely unchanged.

### Why this shape (not per-type duplicated handlers)

- Department/doctor/date/slot picking logic is identical across every type today — duplicating
  those handler bodies into 7 files would be exactly the kind of premature/duplicated code the
  user doesn't want. The step-list keeps mechanics in one place, while giving each type its own
  file as the natural home for whatever *does* diverge (now: which steps to include; later:
  type-specific extra steps/handlers).
- Adding a genuinely new step for one type later (Phase 2 — e.g. a "select test" step for
  `lab.py`) is then a two-line change: add a new state to that type's `steps` tuple, add its
  handler to the shared dispatch dict, done — no other type's file or the shared handlers need
  to change.

## Phase 2 — per-type behavior, one type at a time (confirmed with the user: implement and land
one type at a time, waiting for confirmation before moving to the next)

### Step 1 — New Consultation (`new_consultation.py`) — ✅ DONE

Two New-Consultation-only booking rules, confirmed with the user:
1. A patient cannot have a second ACTIVE (non-cancelled) booking in the SAME department — must
   cancel the existing one first. Enforced right when the department is picked (doesn't need a
   date), so the patient sees the conflict immediately instead of after picking doctor/date/slot.
2. A patient cannot book a DIFFERENT department on a day they already have ANY active booking —
   one active booking per day, regardless of department. Enforced right before the booking is
   actually created, since it needs the chosen date.

**How it was built** — two `TypeFlow` hooks (`flows/booking/types/base.py`):
- `validate_department`: an optional `(connector, hospital_id, patient_id, department_id) -> str | None`
  callable, checked in `book.py`'s `_handle_awaiting_department` right after a department is
  selected (before the doctor menu is even sent). On a conflict, sends the translated message as
  plain text and re-shows the department menu (session stays at `AWAITING_DEPARTMENT`).
- `validate_booking`: an optional `(connector, hospital_id, patient_id, department_id, scheduled_at) -> str | None`
  callable, `None` by default for every type that has nothing extra to check. This is the general
  Phase 2 extension point every subsequent step below plugs into the same way.
- `db/repositories/appointments.py` — new `get_active_appointments_for_patient(hospital_id, patient_id)`
  (STATUS_BOOKED only, scoped by `patient_id` not `phone`, since one phone can have several linked
  patients), exposed through `Connector`/`Tier1Connector`.
- `flows/booking/types/new_consultation.py` — `_validate_new_consultation_department(...)` (rule 1,
  wired to `validate_department`) and `_validate_new_consultation_booking(...)` (both rules, wired
  to `validate_booking` as a same-department safety net plus the same-day check), both against
  `get_active_appointments_for_patient`.
- `flows/booking/book.py` — `_handle_awaiting_department` calls `flow.validate_department(...)`
  right after department selection; `_create_booking_and_notify` calls `flow.validate_booking(...)`
  right after `_reject_if_patient_link_invalid` and before `connector.create_booking(...)` (context
  can still change up to that exact point via "change selection," so a same-department re-check
  here too, not just at department-selection time).
- `core/translations.py` — `new_consultation_department_conflict` / `new_consultation_same_day_conflict`
  (en/hi).

### Step 2 — Follow-up (`followup.py`) — ✅ DONE

Confirmed with the user: picking Follow-up skips department/doctor selection entirely and
auto-selects the SAME doctor/department as the patient's most recent **attended** appointment
(not just any past booking — a no-show or a still-upcoming booking doesn't count), then jumps
straight to date selection. No previous attended appointment at all → told, sent back to
appointment-type selection (Follow-up isn't offered without a real prior visit). Every screen
this adds a Back button to, matching the existing convention everywhere else in the flow.

**How it was built** — a new `TypeFlow.on_selected` hook (`flows/booking/types/base.py`): an
optional async `(wa, sessions, phone, hospital_id, connector, new_context, language) -> None`
callable that fully replaces the default "proceed to `steps[0]`" behavior for a type that defines
one. `None` (the default) leaves every other type's existing behavior untouched.
- `db/repositories/appointments.py` — new `get_last_attended_appointment(hospital_id, patient_id)`
  (STATUS_ATTENDED only, most recent by `scheduled_at`), exposed through `Connector`/`Tier1Connector`.
- `flows/booking/types/followup.py` — `_on_followup_selected` (the `on_selected` hook): looks up
  the last attended appointment, stashes its department/doctor + a formatted last-visit label into
  context, and shows a new "Continue with Dr. X (Department)?" confirm screen
  (`STATE_AWAITING_FOLLOWUP_CONFIRM`, Confirm + Back buttons) — or, if there's no last attended
  appointment, sends the "no previous appointment" message and re-shows appointment-type
  selection. Its own state handler (`_handle_awaiting_followup_confirm`) advances straight to
  `STATE_AWAITING_DATE` on Confirm (pushing a history frame first, so Back from date selection
  returns to this same confirm screen, not further back). `steps=NO_DOCTOR_FLOW` (not `FULL_FLOW`)
  so shared bookkeeping (the change-selection menu) correctly hides "Change Department"/"Change
  Doctor" here too, same as diagnostic/lab.
- `flows/booking/book.py` — `_handle_awaiting_appointment_type` checks `flow.on_selected` first,
  before the existing NO_DOCTOR_FLOW department-skip branch.
- `flows/booking/messages.py` — `_resend_menu_for_state` gained a case for
  `STATE_AWAITING_FOLLOWUP_CONFIRM` (lazy-imports `followup.py`, avoiding a cycle back through
  `types.registry`), so a Back-navigation landing back on this state re-sends the confirm prompt
  instead of going silent.
- `flows/booking/dispatch.py` — registers the new state's handler in the shared `_HANDLERS` dict
  (flows through to `flows/booking/__init__.py`'s `HANDLERS` and `flows/router.py`'s
  `_BOOKING_STATE_HANDLERS` automatically, no separate registration needed there).
- `core/translations.py` — `no_previous_appointment_for_followup` / `followup_confirm_prompt` (en/hi).
- Tests: `tests/test_booking_flow.py`'s `test_followup_with_no_previous_visit_sends_back_to_appointment_type`,
  `test_followup_confirm_screen_then_straight_to_date_selection`,
  `test_followup_back_from_date_returns_to_followup_confirm_screen`. Updated
  `tests/test_appointment_type_flows.py` for `followup`'s new `steps`/`on_selected` shape.
- Full backend suite passing except the same pre-existing, unrelated reception-handoff failures.

### Step 3 — Tele Consultation (`tele_consultation.py`) — ✅ DONE

Confirmed with the user: a tele-consultation booking gets a real video-call room generated and
attached, without touching its step list at all (`steps=FULL_FLOW`, unchanged). Revised mid-build
per the user's own explicit "soft-gate" call: the link is generated and persisted at booking time,
but deliberately **not shown** in the immediate booking-confirmation message — it's surfaced later,
close to the actual slot, via the reminder message instead, so a patient can't casually share or
join a "live" room hours or days early.

**How it was built** — a new `TypeFlow.on_booking_confirmed` hook (`flows/booking/types/base.py`):
an optional async `(appointment_id, hospital_id, patient_id, connector) -> dict | None` callable
run right after `connector.create_booking()` succeeds. `None` (the default) leaves every other
type's notification untouched.
- `db/orm_models.py` / `db/schema.sql` / `db/migrations/versions/0004_appointment_video_link.py` /
  `db/init_db.py` — new `appointments.video_link` column (nullable, `TEXT`), non-tele rows always
  `NULL`.
- `db/repositories/appointments.py` — new `set_appointment_video_link(hospital_id, appointment_id,
  video_link)`; existing appointment-read query/`db/models.py`'s `Appointment` now carry
  `video_link` through.
- `connectors/base.py` / `connectors/tier1.py` — `set_appointment_video_link` added to the
  `Connector` protocol and `Tier1Connector` implementation.
- `flows/booking/types/tele_consultation.py` — `_on_tele_booking_confirmed` (the
  `on_booking_confirmed` hook): builds a Jitsi Meet URL (`https://meet.jit.si/CareConnect-<token>`)
  with a fresh `secrets.token_urlsafe(24)` CSPRNG token per booking (never derived from appointment
  id/timestamp/patient info, so it can't be guessed or enumerated — Jitsi has no auth, the room
  name itself is the access control), persists it via `set_appointment_video_link`, and returns
  `{"video_link": ...}`. `FLOW = TypeFlow(type_id="tele", steps=FULL_FLOW,
  on_booking_confirmed=_on_tele_booking_confirmed)`.
- `flows/booking/book.py` — `_create_booking_and_notify` calls `flow.on_booking_confirmed(...)`
  right after `create_appointment()` succeeds, before building the confirmation summary; per the
  soft-gate revision, the returned dict is no longer consulted here (the confirmation text is
  identical to every other type).
- `flows/booking/reschedule.py` — rescheduling creates a genuinely new appointment row that
  inherits the old row's `appointment_type_id` but not its `video_link` (a room is tied to a
  specific slot, not carried across a date/time change), so the reschedule success path
  re-resolves `get_type_flow(new_appointment.appointment_type_id)` and re-runs
  `on_booking_confirmed` for the new row — otherwise a rescheduled tele-consultation's reminder
  would have no link.
- `reminders/scheduler.py` — the reminder builder appends the video link line only when
  `appointment_type_id == "tele"` and `video_link` is set (handles the gap between booking and the
  hook actually persisting it, and any pre-existing row from before this migration).
- `portal/routes/bookings.py` — surfaces `video_link` in the admin/portal booking payload (`None`
  for every non-tele row).
- Tests: `tests/test_booking_flow.py`'s `test_tele_consultation_booking_generates_and_stores_a_video_link`,
  `test_tele_consultation_video_link_token_is_not_predictable`,
  `test_non_tele_types_get_no_video_link_in_their_confirmation`,
  `test_rescheduling_a_tele_consultation_generates_a_fresh_video_link`; `tests/test_reminders.py`'s
  `test_tele_appointment_reminder_includes_video_link`,
  `test_non_tele_appointment_reminder_has_no_video_link`,
  `test_tele_appointment_with_no_video_link_yet_gets_plain_reminder`.
- Full backend suite passing except the same pre-existing, unrelated reception-handoff failures.

### Step 4 — Daycare (`daycare.py`) — ✅ DONE

Confirmed with the user directly (a short design discussion, not assumed): the original Phase-1
placeholder plan ("replace time-slot with a date-range step") was revised once the user raised that
some daycare stays are only a few hours, not a multi-day range. Final shape: the existing
department→doctor→date→time-slot pickers are kept completely unchanged (a daycare patient still
needs a real arrival slot), and exactly ONE new step is inserted after time-slot and before
confirmation — picking a stay-length option from a **hospital-configurable** list (not a fixed
enum — confirmed with the user: a same-day 6-hour stay and a 2-night admission both need to be
expressible, and hospitals price/label these differently).

**How it was built**:
- `flows/booking/state.py` — new `STATE_AWAITING_DAYCARE_DURATION` state; new
  `CHANGE_DURATION`/`_CHANGE_TARGETS` entry so the confirmation screen's "what would you like to
  change?" menu can jump straight back to it.
- `flows/booking/types/base.py` — new `TypeFlow.next_step(current) -> str` method (walks `steps`,
  falls back to `STATE_AWAITING_CONFIRMATION` past the end or for an unrecognized state) — the one
  shared transition point (time-slot completion, `book.py`) that previously hardcoded its next
  state directly now calls this, so daycare can insert an extra step there with no
  `if appointment_type_id == "daycare"` branch in shared code. `OnBookingConfirmedHook` extended to
  also receive the live booking `context` (tele's hook ignores it; daycare's needs
  `context["daycare_duration_hours"]`).
- `flows/booking/types/daycare.py` — its own `steps` tuple (`FULL_FLOW` with
  `STATE_AWAITING_DAYCARE_DURATION` inserted before confirmation, kept local rather than in
  `base.py` since no other type reuses it), `_send_daycare_duration_menu` +
  `_handle_awaiting_daycare_duration` (the new state's own handler, registered in
  `dispatch.py`'s `_HANDLERS`), and `_on_daycare_duration_confirmed` (the `on_booking_confirmed`
  hook) which persists the chosen duration via `connector.set_appointment_duration`.
- `db/repositories/daycare_duration_options.py` (new) + `daycare_duration_options` table
  (migration `0008`) — hospital-configurable list (`get_daycare_duration_options` for the active
  subset the WhatsApp flow shows; `get_all_daycare_duration_options_for_hospital` plus
  create/update/toggle/delete for the portal), seeded with 3 defaults ("4-6 hours", "Full day",
  "Overnight (1 night)") per hospital by `db/init_db.py`'s `_backfill_daycare_duration_options`.
  Unlike `appointment_types` (a closed, id-keyed catalog), this is a genuinely open one — a
  hospital can add/relabel/remove its own options, so the backfill only seeds hospitals with zero
  existing rows rather than gating per-row.
- `appointments.duration_hours` (migration `0008`, alongside the new table) — the chosen option's
  `hours`, persisted onto the booking itself so it survives the option later being relabeled or
  deactivated. `db/repositories/appointments.py`'s `create_appointment()` gained an optional
  `duration_hours` param (used only by reschedule's carry-forward below — a fresh booking always
  starts NULL and gets set via the hook after creation, same as tele's `video_link`); new
  `set_appointment_duration(hospital_id, appointment_id, duration_hours)`. `db/models.py`'s
  `Appointment` dataclass and the ORM `AppointmentRow` both carry the new column through.
- `connectors/base.py` / `connectors/tier1.py` — `get_daycare_duration_options` and
  `set_appointment_duration` added to the `Connector` protocol.
- Reschedule handling: unlike tele's video link (deliberately regenerated fresh per slot, since the
  room is tied to a specific booking), daycare's duration isn't slot-specific and the reschedule
  flow never re-asks it. `connectors/tier1.py`'s `reschedule_booking()` carries the ORIGINAL
  appointment's `duration_hours` onto the new row at creation time (same pattern as
  `appointment_type_id`), and `_on_daycare_duration_confirmed` is a no-op when
  `context["daycare_duration_hours"]` is absent (the reschedule call site's context never has it) —
  so the hook only ever acts on a genuinely fresh booking.
- `flows/booking/messages.py` — `_send_confirmation` appends a `⏱ Duration:` line when
  `context["daycare_duration_label"]` is set (shown immediately, unlike tele's link — there's no
  "don't reveal early" concern for a duration choice); `_resend_menu_for_state` and
  `_send_change_selection_menu` both gained the new state/row (lazy-imported, same
  cycle-avoidance as `followup.py`'s case).
- `portal/routes/daycare_duration_options.py` (new) — full CRUD (list/create/update/toggle/delete),
  reusing the existing `manage_appointment_types` capability rather than adding a new one, since
  it's the same portal screen area. No frontend admin page yet — backend-only for this pass, same
  scope boundary Phase 2 has kept type-by-type; flagged here for a follow-up.
- `core/translations.py` — `select_daycare_duration` / `view_durations_button` /
  `daycare_durations_section_title` / `change_duration_option` / `confirm_daycare_duration_line`
  (en/hi).
- Tests: `tests/test_appointment_type_flows.py`'s updated `test_known_types_resolve_to_their_own_flow`
  (daycare's actual step tuple, not `FULL_FLOW`) and new `test_next_step`;
  `tests/test_booking_flow.py`'s `test_daycare_booking_asks_for_duration_and_stores_it`,
  `test_rescheduling_a_daycare_appointment_carries_the_same_duration_forward`, and the shared
  `_book_through_confirmation` helper updated to drive through the new step for every type that has
  it.
- Full backend suite passing (674 tests, no regressions).

### Step 5+ — remaining types (not started, one at a time, each awaiting confirmation first)

Concrete hooks the Phase-1 structure sets up for these, per type file:
- `lab.py` / `diagnostic.py`: insert a new `STATE_AWAITING_TEST_SELECTION` step before
  `STATE_AWAITING_DATE` (pick which test/panel, if the hospital wants that granularity).
- `second_opinion.py`: an optional document-upload step before confirmation.

None of this is implemented yet — listed only so the Phase-1 file layout is judged against where
Phase 2 work will actually land, and each is only started once the user confirms it.

## Files touched (Phase 1)

- `backend/flows/booking/types/base.py` (new), `registry.py` (new), and one small module per
  type (`new_consultation.py`, `followup.py`, `tele_consultation.py`, `second_opinion.py`,
  `daycare.py`, `diagnostic.py`, `lab.py`) (new).
- `backend/flows/booking/book.py` — replace hardcoded next/prev-state transitions with
  `registry.get_type_flow(...)` lookups at the handful of transition points listed above; no
  handler body logic changes.
- `backend/flows/booking/messages.py` — change-selection menu built from `flow.steps`.
- `backend/flows/booking/state.py` — no new states; possibly remove the now-redundant static
  `_CHANGE_TARGETS` dict if fully replaced by `flow.prev_step`.

## Verification

- Existing tests must keep passing unchanged for all types except diagnostic/lab:
  `tests/test_booking_flow.py`, `test_booking_back_navigation.py`, `test_flows.py`.
- Update/add tests asserting diagnostic and lab bookings never see a department or doctor prompt
  and go straight from appointment-type selection to date selection (and that back-navigation
  from date returns to appointment-type selection, not doctor).
- Add a registry unit test: unknown/custom `appointment_type_id` falls back to `FULL_FLOW`.
- Manual: book one of each of the 7 types end-to-end via the dev webhook, confirming
  diagnostic/lab skip department+doctor and every other type's flow is pixel-identical to today.
