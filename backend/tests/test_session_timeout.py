# tests/test_session_timeout.py
"""
Audit + fix verification for the hospital-configurable idle timeout
(hospitals.session_timeout_minutes, Section 12.13) actually counting from
the patient's most recent message, not from when the session/flow
originally started.

Audit finding: core/session_store.py's InMemorySessionStore.set() (and
RedisSessionStore.set()) unconditionally stamps "updated_at": time.time()
on EVERY call, and every core/booking_flow.py state handler -- reached via
flows.py's real router, the actual production entry point, not just
booking_flow.handle_incoming() directly -- calls sessions.set() or
sessions.reset() (which itself calls set() when a language is already
chosen) on every processed message, including free-text re-prompts and
unrecognized taps, not just state ADVANCES. There was no code path found
where a message is handled without touching updated_at. This was already
correct before this file existed; the tests below prove it empirically
(via a controlled fake clock, not real sleeps) rather than trusting the
reading, and exist so a future regression here gets caught immediately.
"""
import core.session_store as history_module
import db.repository as db
import flows

PHONE = "5491112345678"


class FakeWhatsAppClient:
    def __init__(self):
        self.sent = []

    async def send_text(self, to, text):
        self.sent.append(("text", {"to": to, "text": text}))

    async def send_list(self, to, body_text, button_text, sections, header_text=None, footer_text=None):
        self.sent.append(("list", {"to": to, "body_text": body_text, "sections": sections}))

    async def send_buttons(self, to, body_text, buttons, header_text=None, footer_text=None):
        self.sent.append(("buttons", {"to": to, "body_text": body_text, "buttons": buttons}))


def tap(option_id):
    return {"type": "interactive_reply", "id": option_id, "title": ""}


def text_reply(text):
    return {"type": "text", "text": text}


class _FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def time(self):
        return self.now


async def test_activity_every_90s_over_5_minutes_never_times_out_at_2_minute_setting(hospital_id, monkeypatch):
    """The exact scenario requested: a patient responding every 90 seconds
    (each gap well under the 2-minute/120s setting) across a 5-minute
    conversation must never be treated as timed out, even though the TOTAL
    elapsed time since their first message (270s) exceeds 120s -- only the
    gap between consecutive messages matters."""
    clock = _FakeClock(start=1_000_000.0)
    monkeypatch.setattr(history_module.time, "time", clock.time)

    wa = FakeWhatsAppClient()
    sessions = history_module.InMemorySessionStore()
    # Skip the language picker (unrelated to this test) -- same shortcut
    # test_hospital_settings.py's own timeout test already uses.
    sessions.set(hospital_id, PHONE, "IDLE", {}, language="en")

    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    common_kwargs = dict(
        hospital_name="City Hospital", enabled_features=["booking"], session_timeout_minutes=2,
    )

    # t=0: Book -> name prompt (Patient identity/UX follow-up, Spec.md
    # Section 0: name/age is now collected first, before department).
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), **common_kwargs)
    assert sessions.get(hospital_id, PHONE, timeout_seconds=120)["state"] == "AWAITING_PATIENT_NAME"

    # t=90 (gap 90s, under the 120s limit): give name -> age prompt
    clock.now += 90
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"), **common_kwargs)
    assert sessions.get(hospital_id, PHONE, timeout_seconds=120)["state"] == "AWAITING_PATIENT_AGE"

    # t=180 (gap 90s): give age -> appointment type list
    clock.now += 90
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"), **common_kwargs)
    assert sessions.get(hospital_id, PHONE, timeout_seconds=120)["state"] == "AWAITING_APPOINTMENT_TYPE"

    # t=270 (gap 90s): pick appointment type -> department list
    clock.now += 90
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), **common_kwargs)
    assert sessions.get(hospital_id, PHONE, timeout_seconds=120)["state"] == "AWAITING_DEPARTMENT"

    # t=360 (gap 90s): pick department -> doctor list
    clock.now += 90
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"), **common_kwargs)
    session = sessions.get(hospital_id, PHONE, timeout_seconds=120)
    assert session["state"] == "AWAITING_DOCTOR"
    assert session["context"]["department_id"] == "cardiology"

    # t=450 (gap 90s): pick doctor -> date list
    clock.now += 90
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), **common_kwargs)
    session = sessions.get(hospital_id, PHONE, timeout_seconds=120)
    assert session["state"] == "AWAITING_DATE"
    assert session["context"]["doctor_id"] == doctor_id

    # t=540 (gap 90s, total elapsed since t=0 is 540s -- well past 120s, but
    # every individual gap stayed under it): still alive.
    clock.now += 90
    slots = db.get_slots(hospital_id, doctor_id)
    date_str = slots[0]["date"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(date_str), **common_kwargs)
    session = sessions.get(hospital_id, PHONE, timeout_seconds=120)
    assert session["state"] == "AWAITING_TIME_SLOT"
    assert session["context"]["date"] == date_str
    # Never fell back to the main menu at any point along the way.
    assert not any(
        kind == "list" and "Main Menu" in kwargs.get("sections", [{}])[0].get("title", "")
        for kind, kwargs in wa.sent
    )


async def test_genuine_2_minute_silence_times_out_and_resets_to_idle(hospital_id, monkeypatch):
    """Same setting, same flow -- but this time a real 130-second gap (over
    the 120s/2-minute limit) between two messages. The next message must be
    treated as a fresh conversation (IDLE), not resumed mid-flow."""
    clock = _FakeClock(start=2_000_000.0)
    monkeypatch.setattr(history_module.time, "time", clock.time)

    wa = FakeWhatsAppClient()
    sessions = history_module.InMemorySessionStore()
    sessions.set(hospital_id, PHONE, "IDLE", {}, language="en")
    common_kwargs = dict(
        hospital_name="City Hospital", enabled_features=["booking"], session_timeout_minutes=2,
    )

    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("menu_book"), **common_kwargs)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("Ravi Kumar"), **common_kwargs)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, text_reply("34"), **common_kwargs)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("new"), **common_kwargs)
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap("cardiology"), **common_kwargs)
    assert sessions.get(hospital_id, PHONE, timeout_seconds=120)["state"] == "AWAITING_DOCTOR"

    # Goes silent for 130 seconds (over the 120s limit).
    clock.now += 130
    wa.sent.clear()
    doctor_id = db.get_doctors(hospital_id, "cardiology")[0]["id"]
    await flows.handle_incoming(wa, sessions, PHONE, hospital_id, tap(doctor_id), **common_kwargs)

    # Treated as a stale/expired session: the tapped doctor id (a real, valid
    # AWAITING_DOCTOR reply) is NOT accepted as a doctor selection -- it's an
    # unrecognized id against a fresh session, so the bot falls back to a
    # genuinely fresh conversation (the language picker, per Section 12.11's
    # own "ask again after a real gap" design -- not straight to the main
    # menu) instead of silently continuing the old flow.
    session = sessions.get(hospital_id, PHONE, timeout_seconds=120)
    assert session["state"] == "AWAITING_LANGUAGE"
    assert session["context"] == {}
    kind, kwargs = wa.sent[-1]
    assert kind == "buttons"
    button_ids = {b["id"] for b in kwargs["buttons"]}
    assert button_ids == {"lang_en", "lang_hi"}  # the language picker, not a doctor list
