# connectors/base.py
"""
SPEC Section 12.6.2: the fixed connector interface. core/booking_flow.py and
reminders/scheduler.py call ONLY through this interface, never db/repository.py
directly — a hospital's stored data_tier (Tier 1/2/3, Section 12.6) is
resolved to a concrete connector exactly once, at the single dispatch point
in connectors/dispatch.py (get_connector_for_hospital), called by
core/main.py right after it resolves the hospital (the webhook handler, the
reminder loop) — not as tier-checks scattered through the booking flow
itself.

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

Section 12.11 (patient name/age collection during WhatsApp booking) adds
`get_patient_info` and a `patient_age` param on `create_booking` — the "have
we already met this patient" read core/booking_flow.py needs before deciding
whether to ask for a name/age is exactly the kind of per-tier-varying data
access this interface exists to abstract (a Tier 2/3 hospital's own system
may or may not have an equivalent concept), so it goes through here rather
than booking_flow.py reaching into db/repository.py directly for it.

ARCHITECTURE_PLAN.md Phase 2: split out of the former single connectors.py
module. This file holds only the abstract contract, the shared "not
implemented yet" stub base, and its error type — concrete tiers live in
connectors/tier1.py, tier2.py, tier3.py; dispatch lives in
connectors/dispatch.py.
"""
import abc
from datetime import datetime

from db.models import Appointment


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
        source: str = "whatsapp", patient_name: str | None = None, patient_age: int | None = None,
        patient_id: int | None = None,
    ) -> Appointment: ...

    @abc.abstractmethod
    def get_patient_info(self, hospital_id: int, phone: str) -> dict | None: ...

    @abc.abstractmethod
    def list_active_patients(self, hospital_id: int, phone: str) -> list[dict]: ...

    @abc.abstractmethod
    def create_patient_profile(
        self, hospital_id: int, phone: str, name: str, age: int | None, relationship_label: str | None = None,
    ) -> dict: ...

    @abc.abstractmethod
    def unlink_patient(self, hospital_id: int, phone: str, patient_id: int) -> bool: ...

    @abc.abstractmethod
    def find_potential_duplicate_patient(self, hospital_id: int, phone: str, name: str, age: int | None) -> dict | None: ...

    @abc.abstractmethod
    def link_existing_patient(
        self, hospital_id: int, phone: str, patient_id: int, relationship_label: str | None = None,
    ) -> dict: ...

    @abc.abstractmethod
    def validate_active_patient_link(self, hospital_id: int, phone: str, patient_id: int) -> bool: ...

    @abc.abstractmethod
    def get_patient_link_consent(self, hospital_id: int, phone: str, patient_id: int) -> dict | None: ...

    @abc.abstractmethod
    def set_marketing_consent(self, hospital_id: int, phone: str, patient_id: int, consented: bool) -> bool: ...

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
        patient_id: int | None = None,
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

    def create_booking(self, hospital_id, phone, department_id, doctor_id, scheduled_at, source="whatsapp", patient_name=None, patient_age=None, patient_id=None):
        self._not_implemented("create_booking")

    def get_patient_info(self, hospital_id, phone):
        self._not_implemented("get_patient_info")

    def list_active_patients(self, hospital_id, phone):
        self._not_implemented("list_active_patients")

    def create_patient_profile(self, hospital_id, phone, name, age, relationship_label=None):
        self._not_implemented("create_patient_profile")

    def unlink_patient(self, hospital_id, phone, patient_id):
        self._not_implemented("unlink_patient")

    def find_potential_duplicate_patient(self, hospital_id, phone, name, age):
        self._not_implemented("find_potential_duplicate_patient")

    def link_existing_patient(self, hospital_id, phone, patient_id, relationship_label=None):
        self._not_implemented("link_existing_patient")

    def validate_active_patient_link(self, hospital_id, phone, patient_id):
        self._not_implemented("validate_active_patient_link")

    def get_patient_link_consent(self, hospital_id, phone, patient_id):
        self._not_implemented("get_patient_link_consent")

    def set_marketing_consent(self, hospital_id, phone, patient_id, consented):
        self._not_implemented("set_marketing_consent")

    def cancel_booking(self, hospital_id, appointment_id):
        self._not_implemented("cancel_booking")

    def reschedule_booking(self, hospital_id, old_appointment_id, phone, department_id, doctor_id, scheduled_at, patient_id=None):
        self._not_implemented("reschedule_booking")

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        self._not_implemented("get_upcoming_appointments")

    def mark_reminder_sent(self, hospital_id, appointment_id, offset_hours):
        self._not_implemented("mark_reminder_sent")
