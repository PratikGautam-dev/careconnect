# core/flow_common.py
"""
Shared helpers used by every flow_type handler module (SPEC Section 14.1) --
core/booking_flow.py and faq_flow.py both import from here rather than each
reimplementing the same fixes. Extracted out of core/booking_flow.py
specifically because Section 14's second flow type (FAQ) is exactly the case
this was for: a fix made once, in one flow, needs to actually apply to every
flow, not just the one it happened to be found in first.
"""
import logging

logger = logging.getLogger(__name__)

# Meta hard-limits a WhatsApp interactive list message to 10 rows total across
# every section (core/whatsapp.py:send_list()'s own docstring already says
# so) -- nothing enforced that until this was found live: a doctor with a long
# working-hour range and a short slot duration can easily generate 100+
# bookable slots (Section 12.1.1), and an unenforced-limit send silently fails
# end to end -- send_list() catches the resulting 400 from Meta, logs it, and
# returns without raising, so the patient just sees nothing, with no error
# surfaced anywhere they'd see it. cap_rows() is the one place this gets
# enforced, applied at every send_list() call site that builds its rows from
# a variable-length source (departments/doctors/slots/appointments/FAQ topics).
MAX_LIST_ROWS = 10


def cap_rows(rows: list[dict], context: str) -> list[dict]:
    if len(rows) > MAX_LIST_ROWS:
        logger.warning(
            "%s: %d rows exceeds WhatsApp's %d-row list limit -- truncating to the first %d",
            context, len(rows), MAX_LIST_ROWS, MAX_LIST_ROWS,
        )
        return rows[:MAX_LIST_ROWS]
    return rows


# A patient can always escape a stuck or confusing mid-flow state by typing
# one of these, regardless of which state/flow they're in -- without this, the
# only ways out of a stuck state were correctly tapping a list option or
# waiting out the 30-minute session timeout (core/history.py), and neither is
# a real patient's first instinct when a bot stops responding. Matches common
# WhatsApp bot convention.
RESET_KEYWORDS = {"hi", "hello", "hey", "menu", "start", "restart"}


def is_reset_keyword(reply: dict) -> bool:
    return reply["type"] == "text" and reply["text"].strip().lower() in RESET_KEYWORDS
