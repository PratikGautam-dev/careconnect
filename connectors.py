# connectors.py
"""
SPEC Section 12.6.2: the fixed connector interface. core/booking_flow.py and
reminders/scheduler.py call ONLY through this interface, never db/repository.py
directly — a hospital's stored data_tier (Tier 1/2/3, Section 12.6) is
resolved to a concrete connector exactly once, at the single dispatch point
below (get_connector_for_hospital), called by core/main.py right after it
resolves the hospital (the webhook handler, the reminder loop) — not as
tier-checks scattered through the booking flow itself.

Connector instances are stateless and shared across every hospital of a given
tier (like db/repository.py's plain functions) — every method takes
hospital_id explicitly rather than binding a connector to one hospital, so
there's no per-hospital connector cache to maintain (unlike core/main.py's
_wa_clients, which genuinely needs one WhatsAppClient per hospital's own
credentials).

Two methods here (get_upcoming_appointments' phone=/offset_hours= modes, and
mark_reminder_sent) go slightly beyond the 7 names in Section 12.6.2's
contract as originally listed — reminders/scheduler.py's no-double-send
guarantee (SPEC Section 4, the Phase 9 follow-up) has no home otherwise, and
folding "which appointments are due" into one method with two filtering modes
was the least-new-surface way to cover both booking_flow.py's (patient-scoped)
and reminders/scheduler.py's (offset-scoped) needs with a single name.
"""
import abc
from datetime import datetime

import db.repository as repo
from db.repository import Appointment, Hospital


class ConnectorNotImplementedError(NotImplementedError):
    """Raised when a hospital is configured for a data_tier (Tier 2/3, SPEC
    Section 12.6) that has no real connector implementation yet. Deliberately
    its own type (not a bare NotImplementedError) so callers/logs can tell
    "this tier isn't built yet" apart from an actual programming bug."""


class Connector(abc.ABC):
    """The fixed contract (SPEC Section 12.6.2)."""

    @abc.abstractmethod
    def get_departments(self, hospital_id: int) -> list[dict]: ...

    @abc.abstractmethod
    def get_doctors(self, hospital_id: int, department_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_available_slots(self, hospital_id: int, doctor_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def create_booking(
        self, hospital_id: int, phone: str, department_id: str, doctor_id: str, scheduled_at: datetime,
        source: str = "whatsapp", patient_name: str | None = None,
    ) -> Appointment: ...

    @abc.abstractmethod
    def cancel_booking(self, hospital_id: int, appointment_id: int) -> None: ...

    @abc.abstractmethod
    def reschedule_booking(
        self,
        hospital_id: int,
        old_appointment_id: int,
        phone: str,
        department_id: str,
        doctor_id: str,
        scheduled_at: datetime,
    ) -> Appointment: ...

    @abc.abstractmethod
    def get_upcoming_appointments(
        self,
        hospital_id: int,
        phone: str | None = None,
        offset_hours: float | None = None,
        now: datetime | None = None,
    ) -> list[Appointment]: ...

    @abc.abstractmethod
    def mark_reminder_sent(self, hospital_id: int, appointment_id: int, offset_hours: float) -> None: ...


class Tier1Connector(Connector):
    """SPEC Section 12.6 Tier 1 — this product's own database. Thin wrapper
    around db/repository.py; the only tier with a real implementation."""

    def get_departments(self, hospital_id):
        return repo.get_departments(hospital_id)

    def get_doctors(self, hospital_id, department_id):
        return repo.get_doctors(hospital_id, department_id)

    def get_available_slots(self, hospital_id, doctor_id):
        return repo.get_slots(hospital_id, doctor_id)

    def create_booking(self, hospital_id, phone, department_id, doctor_id, scheduled_at, source="whatsapp", patient_name=None):
        return repo.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at, source=source, patient_name=patient_name)

    def cancel_booking(self, hospital_id, appointment_id):
        repo.cancel_appointment(hospital_id, appointment_id)

    def reschedule_booking(self, hospital_id, old_appointment_id, phone, department_id, doctor_id, scheduled_at):
        """Books the new slot BEFORE marking the old appointment rescheduled:
        if someone else grabbed this exact doctor+slot first (IntegrityError,
        left to propagate uncaught to the caller — same as create_booking),
        the patient keeps their original appointment rather than being left
        with neither. This ordering is a deliberate Phase 8 fix, now living
        here instead of split across two separate core/booking_flow.py calls."""
        new_appointment = repo.create_appointment(hospital_id, phone, department_id, doctor_id, scheduled_at)
        repo.mark_rescheduled(hospital_id, old_appointment_id)
        return new_appointment

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        if phone is not None:
            return repo.get_upcoming_appointments_for_phone(hospital_id, phone, now=now)
        if offset_hours is not None:
            return repo.get_upcoming_appointments(hospital_id, offset_hours, now=now)
        raise ValueError("get_upcoming_appointments requires either phone= or offset_hours=")

    def mark_reminder_sent(self, hospital_id, appointment_id, offset_hours):
        repo.mark_reminded(hospital_id, appointment_id, offset_hours)


class _UnimplementedTierConnector(Connector):
    """Shared stub base for tiers with no real connector yet — every method
    raises the same clear, descriptive error rather than building speculative
    connector logic ahead of a real hospital on that tier existing (SPEC
    Section 12.6's own guidance: build Tier 2 only against a real hospital's
    actual API shape; Tier 3 is a manually-assisted case-by-case engagement)."""

    _tier_label: str

    def _not_implemented(self, method_name: str):
        raise ConnectorNotImplementedError(
            f"{self._tier_label} has no real connector implementation yet (SPEC Section 12.6) — "
            f"'{method_name}' was called for a hospital configured on this tier. This is expected "
            f"to fail loudly: build the real connector against that hospital's actual system before "
            f"onboarding it onto this tier, rather than guessing at one ahead of time."
        )

    def get_departments(self, hospital_id):
        self._not_implemented("get_departments")

    def get_doctors(self, hospital_id, department_id):
        self._not_implemented("get_doctors")

    def get_available_slots(self, hospital_id, doctor_id):
        self._not_implemented("get_available_slots")

    def create_booking(self, hospital_id, phone, department_id, doctor_id, scheduled_at, source="whatsapp", patient_name=None):
        self._not_implemented("create_booking")

    def cancel_booking(self, hospital_id, appointment_id):
        self._not_implemented("cancel_booking")

    def reschedule_booking(self, hospital_id, old_appointment_id, phone, department_id, doctor_id, scheduled_at):
        self._not_implemented("reschedule_booking")

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        self._not_implemented("get_upcoming_appointments")

    def mark_reminder_sent(self, hospital_id, appointment_id, offset_hours):
        self._not_implemented("mark_reminder_sent")


class Tier2Connector(_UnimplementedTierConnector):
    """SPEC Section 12.6 Tier 2 — integration against a hospital's existing
    API. Stubbed on purpose: build only once a real Tier 2 hospital exists,
    against their actual documented API shape."""

    _tier_label = "Tier 2 (external API integration)"


class Tier3Connector(_UnimplementedTierConnector):
    """SPEC Section 12.6 Tier 3 — direct database connection. Stubbed on
    purpose: a manually-assisted, case-by-case engagement, not something to
    build generically ahead of a real hospital needing it."""

    _tier_label = "Tier 3 (direct database connection)"


# Stateless singletons — see module docstring for why one instance per tier
# (not per hospital) is sufficient.
_TIER1 = Tier1Connector()
_TIER2 = Tier2Connector()
_TIER3 = Tier3Connector()

_CONNECTORS_BY_TIER: dict[str, Connector] = {
    "tier1": _TIER1,
    "tier2": _TIER2,
    "tier3": _TIER3,
}


def get_connector_for_hospital(hospital: Hospital) -> Connector:
    """The single dispatch point (SPEC Section 12.6.2). core/main.py calls
    this exactly once per hospital resolution — in the webhook handler right
    after resolving the hospital, and once per hospital in the reminder/slot
    loops — and passes the resulting connector down; core/booking_flow.py and
    reminders/scheduler.py never inspect hospital.data_tier themselves."""
    connector = _CONNECTORS_BY_TIER.get(hospital.data_tier)
    if connector is None:
        raise ConnectorNotImplementedError(
            f'Unrecognized data_tier "{hospital.data_tier}" for hospital {hospital.id} — '
            f'expected one of {sorted(_CONNECTORS_BY_TIER)}.'
        )
    return connector
