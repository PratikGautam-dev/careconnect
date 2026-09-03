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
from typing import NoReturn

from db.models import Appointment


class ConnectorNotImplementedError(NotImplementedError):
    """Raised when a hospital is configured for a data_tier (Tier 2/3, SPEC
    Section 12.6) that has no real connector implementation yet. Deliberately
    its own type (not a bare NotImplementedError) so callers/logs can tell
    "this tier isn't built yet" apart from an actual programming bug."""


class Connector(abc.ABC):
    """The fixed contract (SPEC Section 12.6.2)."""

    # Deliberately no hospital_id param, unlike every other method here --
    # CareConnect account/identity resolution (db/schema.sql's own comment on
    # care_connect_accounts) is a GLOBAL operation, not a per-hospital one; a
    # person's WhatsApp identity is the same regardless of which hospital's
    # bot received the message. See db/repositories/accounts.py.
    @abc.abstractmethod
    def identify_contact(self, provider_user_id: str, phone_number: str | None = None, username: str | None = None) -> dict: ...

    # Same "deliberately no hospital_id param" reasoning as identify_contact
    # above -- db/repositories/platform_settings.py's max_active_patient_links
    # is a single GLOBAL value (a platform/super admin setting, confirmed
    # NOT per-hospital), not something that varies by which hospital's
    # patient-linking cap is being checked.
    @abc.abstractmethod
    def get_max_active_patient_links(self) -> int: ...

    # Same "deliberately no hospital_id param" reasoning as identify_contact
    # above -- a chosen language is GLOBAL to the account (confirmed with
    # the user), not per-hospital like dpdp_consents.
    @abc.abstractmethod
    def set_account_language(self, care_connect_account_id: int, language: str) -> None: ...

    @abc.abstractmethod
    def get_appointment_types(self, hospital_id: int) -> list[dict]: ...

    @abc.abstractmethod
    def get_daycare_duration_options(self, hospital_id: int) -> list[dict]: ...

    @abc.abstractmethod
    def get_departments(self, hospital_id: int) -> list[dict]: ...

    @abc.abstractmethod
    def get_doctors(self, hospital_id: int, department_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_available_slots(self, hospital_id: int, doctor_id: str) -> list[dict]: ...

    # Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
    # the resource-keyed sibling of get_available_slots above.
    @abc.abstractmethod
    def get_available_resource_slots(self, hospital_id: int, resource_id: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_diagnostic_tests(self, hospital_id: int, category: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_diagnostic_resources(self, hospital_id: int) -> list[dict]: ...

    @abc.abstractmethod
    def create_booking(
        self, hospital_id: int, phone: str, department_id: str, doctor_id: str | None, scheduled_at: datetime,
        source: str = "whatsapp", patient_name: str | None = None, patient_age: int | None = None,
        patient_id: int | None = None, appointment_type_id: str | None = None,
        consent_given_at: str | None = None, resource_id: str | None = None,
        diagnostic_test_id: int | None = None, diagnostic_test_variant_id: int | None = None,
        diagnostic_test_label: str | None = None, diagnostic_variant_label: str | None = None,
        diagnostic_price: float | None = None,
    ) -> Appointment: ...

    @abc.abstractmethod
    def get_active_appointments_for_patient(self, hospital_id: int, patient_id: int) -> list[Appointment]: ...

    @abc.abstractmethod
    def get_last_attended_appointment(self, hospital_id: int, patient_id: int) -> Appointment | None: ...

    @abc.abstractmethod
    def get_followup_eligible_appointments(self, hospital_id: int, patient_id: int, validity_days: int) -> list[Appointment]: ...

    @abc.abstractmethod
    def get_patient_info(self, hospital_id: int, phone: str) -> dict | None: ...

    @abc.abstractmethod
    def list_active_patients(self, hospital_id: int, phone: str) -> list[dict]: ...

    @abc.abstractmethod
    def create_patient_profile(
        self, hospital_id: int, phone: str, name: str, age: int | None, relationship_label: str | None = None,
        gender: str | None = None, contact_phone: str | None = None,
    ) -> dict: ...

    # "Myself / Someone Else" registration step (flows/patient_identity.py):
    # deliberately no hospital-scoped `phone` param, same "genuinely global"
    # reasoning as identify_contact()/get_max_active_patient_links() above --
    # the caller already resolved care_connect_account_id via
    # identify_contact() before this point.
    @abc.abstractmethod
    def has_self_linked_patient(self, hospital_id: int, care_connect_account_id: int) -> bool: ...

    @abc.abstractmethod
    def unlink_patient(self, hospital_id: int, phone: str, patient_id: int) -> bool: ...

    @abc.abstractmethod
    def find_potential_duplicate_patient(
        self, hospital_id: int, name: str, contact_phone: str, age: int, gender: str,
    ) -> dict | None: ...

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
    def set_appointment_video_link(self, hospital_id: int, appointment_id: int, video_link: str) -> None: ...

    @abc.abstractmethod
    def set_appointment_duration(self, hospital_id: int, appointment_id: int, duration_hours: int) -> None: ...

    @abc.abstractmethod
    def set_appointment_diagnostic_details(
        self, hospital_id: int, appointment_id: int, diagnostic_test_id: int, diagnostic_test_variant_id: int,
        diagnostic_test_label: str, diagnostic_variant_label: str, diagnostic_price: float | None,
    ) -> None: ...

    @abc.abstractmethod
    def reschedule_booking(
        self,
        hospital_id: int,
        old_appointment_id: int,
        phone: str,
        department_id: str,
        doctor_id: str | None,
        scheduled_at: datetime,
        patient_id: int | None = None,
        resource_id: str | None = None,
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

    @abc.abstractmethod
    def get_appointments_in_range(
        self,
        hospital_id: int,
        care_connect_account_id: int,
        range_start: datetime,
        range_end: datetime,
        statuses: list[str] | None = None,
    ) -> list[Appointment]:
        """"My Appointments" -> Previous/Upcoming 1 Month range view.
        Deliberately keyed on care_connect_account_id, not phone -- see
        db/repositories/appointments.py's get_appointments_for_account_in_range
        for why (a person's WhatsApp number can change while their account
        persists; appointments.phone only records what was used at booking
        time). Callers resolve the account first via identify_contact()."""
        ...


class _UnimplementedTierConnector(Connector):
    """Shared stub base for tiers with no real connector yet — every method
    raises the same clear, descriptive error rather than building speculative
    connector logic ahead of a real hospital on that tier existing (SPEC
    Section 12.6's own guidance: build Tier 2 only against a real hospital's
    actual API shape; Tier 3 is a manually-assisted case-by-case engagement)."""

    _tier_label: str

    def _not_implemented(self, method_name: str) -> NoReturn:
        raise ConnectorNotImplementedError(
            f"{self._tier_label} has no real connector implementation yet (SPEC Section 12.6) — "
            f"'{method_name}' was called for a hospital configured on this tier. This is expected "
            f"to fail loudly: build the real connector against that hospital's actual system before "
            f"onboarding it onto this tier, rather than guessing at one ahead of time."
        )

    def identify_contact(self, provider_user_id, phone_number=None, username=None):
        self._not_implemented("identify_contact")

    def get_max_active_patient_links(self):
        self._not_implemented("get_max_active_patient_links")

    def set_account_language(self, care_connect_account_id, language):
        self._not_implemented("set_account_language")

    def get_appointment_types(self, hospital_id):
        self._not_implemented("get_appointment_types")

    def get_daycare_duration_options(self, hospital_id):
        self._not_implemented("get_daycare_duration_options")

    def get_departments(self, hospital_id):
        self._not_implemented("get_departments")

    def get_doctors(self, hospital_id, department_id):
        self._not_implemented("get_doctors")

    def get_available_slots(self, hospital_id, doctor_id):
        self._not_implemented("get_available_slots")

    def get_available_resource_slots(self, hospital_id, resource_id):
        self._not_implemented("get_available_resource_slots")

    def get_diagnostic_tests(self, hospital_id, category):
        self._not_implemented("get_diagnostic_tests")

    def get_diagnostic_resources(self, hospital_id):
        self._not_implemented("get_diagnostic_resources")

    def create_booking(self, hospital_id, phone, department_id, doctor_id, scheduled_at, source="whatsapp", patient_name=None, patient_age=None, patient_id=None, appointment_type_id=None, consent_given_at=None, resource_id=None, diagnostic_test_id=None, diagnostic_test_variant_id=None, diagnostic_test_label=None, diagnostic_variant_label=None, diagnostic_price=None):
        self._not_implemented("create_booking")

    def get_active_appointments_for_patient(self, hospital_id, patient_id):
        self._not_implemented("get_active_appointments_for_patient")

    def get_last_attended_appointment(self, hospital_id, patient_id):
        self._not_implemented("get_last_attended_appointment")

    def get_followup_eligible_appointments(self, hospital_id, patient_id, validity_days):
        self._not_implemented("get_followup_eligible_appointments")

    def get_patient_info(self, hospital_id, phone):
        self._not_implemented("get_patient_info")

    def list_active_patients(self, hospital_id, phone):
        self._not_implemented("list_active_patients")

    def create_patient_profile(self, hospital_id, phone, name, age, relationship_label=None, gender=None, contact_phone=None):
        self._not_implemented("create_patient_profile")

    def has_self_linked_patient(self, hospital_id, care_connect_account_id):
        self._not_implemented("has_self_linked_patient")

    def unlink_patient(self, hospital_id, phone, patient_id):
        self._not_implemented("unlink_patient")

    def find_potential_duplicate_patient(self, hospital_id, name, contact_phone, age, gender):
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

    def set_appointment_video_link(self, hospital_id, appointment_id, video_link):
        self._not_implemented("set_appointment_video_link")

    def set_appointment_duration(self, hospital_id, appointment_id, duration_hours):
        self._not_implemented("set_appointment_duration")

    def set_appointment_diagnostic_details(self, hospital_id, appointment_id, diagnostic_test_id, diagnostic_test_variant_id, diagnostic_test_label, diagnostic_variant_label, diagnostic_price):
        self._not_implemented("set_appointment_diagnostic_details")

    def reschedule_booking(self, hospital_id, old_appointment_id, phone, department_id, doctor_id, scheduled_at, patient_id=None, resource_id=None):
        self._not_implemented("reschedule_booking")

    def get_upcoming_appointments(self, hospital_id, phone=None, offset_hours=None, now=None):
        self._not_implemented("get_upcoming_appointments")

    def mark_reminder_sent(self, hospital_id, appointment_id, offset_hours):
        self._not_implemented("mark_reminder_sent")

    def get_appointments_in_range(self, hospital_id, care_connect_account_id, range_start, range_end, statuses=None):
        self._not_implemented("get_appointments_in_range")
