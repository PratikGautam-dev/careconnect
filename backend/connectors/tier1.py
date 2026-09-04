# connectors/tier1.py
"""SPEC Section 12.6 Tier 1 — this product's own database. Thin wrapper
around db/repository.py; the only tier with a real implementation.
ARCHITECTURE_PLAN.md Phase 2: split out of the former single connectors.py
module."""
import db.repository as repo

from connectors.base import Connector


class Tier1Connector(Connector):
    def identify_contact(self, provider_user_id, phone_number=None, username=None):
        return repo.get_or_create_account(provider_user_id, phone_number=phone_number, username=username)

    def get_max_active_patient_links(self):
        return repo.get_max_active_patient_links()

    def set_account_language(self, care_connect_account_id, language):
        repo.set_account_language(care_connect_account_id, language)

    def get_appointment_types(self, hospital_id):
        return repo.get_appointment_types(hospital_id)

    def get_departments(self, hospital_id):
        return repo.get_departments(hospital_id)

    def get_doctors(self, hospital_id, department_id):
        return repo.get_doctors(hospital_id, department_id)

    def get_available_slots(self, hospital_id, doctor_id):
        return repo.get_slots(hospital_id, doctor_id)

    def get_available_resource_slots(self, hospital_id, resource_id):
        return repo.get_resource_slots(hospital_id, resource_id)

    def get_diagnostic_tests(self, hospital_id, category):
        return repo.get_diagnostic_tests(hospital_id, category)

    def get_diagnostic_resources(self, hospital_id):
        return repo.get_diagnostic_resources(hospital_id)

    def get_service_areas(self, hospital_id):
        return repo.get_service_areas(hospital_id)

    def is_pincode_serviceable(self, hospital_id, pincode):
        return repo.is_pincode_serviceable(hospital_id, pincode)

    def create_booking(self, hospital_id, phone, department_id, doctor_id, scheduled_at, source="whatsapp", patient_name=None, patient_age=None, patient_id=None, appointment_type_id=None, consent_given_at=None, resource_id=None, diagnostic_test_id=None, diagnostic_test_variant_id=None, diagnostic_test_label=None, diagnostic_variant_label=None, diagnostic_price=None):
        return repo.create_appointment(
            hospital_id, phone, department_id, doctor_id, scheduled_at,
            source=source, patient_name=patient_name, patient_age=patient_age, patient_id=patient_id,
            appointment_type_id=appointment_type_id, consent_given_at=consent_given_at, resource_id=resource_id,
            diagnostic_test_id=diagnostic_test_id, diagnostic_test_variant_id=diagnostic_test_variant_id,
            diagnostic_test_label=diagnostic_test_label, diagnostic_variant_label=diagnostic_variant_label,
            diagnostic_price=diagnostic_price,
        )

    def get_active_appointments_for_patient(self, hospital_id, patient_id):
        return repo.get_active_appointments_for_patient(hospital_id, patient_id)

    def get_last_attended_appointment(self, hospital_id, patient_id):
        return repo.get_last_attended_appointment(hospital_id, patient_id)

    def get_followup_eligible_appointments(self, hospital_id, patient_id, validity_days):
        return repo.get_followup_eligible_appointments(hospital_id, patient_id, validity_days)

    def get_patient_info(self, hospital_id, phone):
        return repo.get_patient_by_phone(hospital_id, phone)

    def list_active_patients(self, hospital_id, phone):
        return repo.get_active_patients_for_phone(hospital_id, phone)

    def create_patient_profile(self, hospital_id, phone, name, age, relationship_label=None, gender=None, contact_phone=None):
        return repo.create_patient_profile(
            hospital_id, phone, name, age, relationship_label=relationship_label, gender=gender,
            contact_phone=contact_phone,
        )

    def has_self_linked_patient(self, hospital_id, care_connect_account_id):
        return repo.has_self_linked_patient(hospital_id, care_connect_account_id)

    def unlink_patient(self, hospital_id, phone, patient_id):
        return repo.unlink_patient(hospital_id, phone, patient_id)

    def find_potential_duplicate_patient(self, hospital_id, name, contact_phone, age, gender):
        return repo.find_potential_duplicate_patient(hospital_id, name, contact_phone, age, gender)

    def link_existing_patient(self, hospital_id, phone, patient_id, relationship_label=None):
        return repo.link_existing_patient(hospital_id, phone, patient_id, relationship_label=relationship_label)

    def validate_active_patient_link(self, hospital_id, phone, patient_id):
        return repo.validate_active_patient_link(hospital_id, phone, patient_id)

    def get_patient_link_consent(self, hospital_id, phone, patient_id):
        return repo.get_patient_link_consent(hospital_id, phone, patient_id)

    def set_marketing_consent(self, hospital_id, phone, patient_id, consented):
        return repo.set_marketing_consent(hospital_id, phone, patient_id, consented)

    def cancel_booking(self, hospital_id, appointment_id):
        repo.cancel_appointment(hospital_id, appointment_id)

    def set_appointment_video_link(self, hospital_id, appointment_id, video_link):
        repo.set_appointment_video_link(hospital_id, appointment_id, video_link)

    def set_appointment_diagnostic_details(self, hospital_id, appointment_id, diagnostic_test_id, diagnostic_test_variant_id, diagnostic_test_label, diagnostic_variant_label, diagnostic_price):
        repo.set_appointment_diagnostic_details(
            hospital_id, appointment_id, diagnostic_test_id, diagnostic_test_variant_id,
            diagnostic_test_label, diagnostic_variant_label, diagnostic_price,
        )

    def set_appointment_lab_order_details(self, hospital_id, appointment_id, collection_method, collection_address, collection_pincode, home_collection_charge, basket_items):
        repo.set_appointment_lab_order_details(
            hospital_id, appointment_id, collection_method, collection_address, collection_pincode,
            home_collection_charge, basket_items,
        )

    def get_lab_basket_for_appointment(self, hospital_id, appointment_id):
        return repo.get_lab_basket_for_appointment(hospital_id, appointment_id)

    def set_lab_status(self, hospital_id, appointment_id, lab_status):
        return repo.set_lab_status(hospital_id, appointment_id, lab_status)

    def get_procedures(self, hospital_id):
        return repo.get_procedures(hospital_id)

    def get_procedure(self, hospital_id, procedure_id):
        return repo.get_procedure(hospital_id, procedure_id)

    def get_procedure_available_slots(self, hospital_id, procedure_id):
        return repo.get_procedure_available_slots(hospital_id, procedure_id)

    def create_procedure_booking(self, hospital_id, phone, procedure_id, scheduled_at, patient_name=None, patient_age=None, patient_id=None, procedure_order_reference=None):
        return repo.create_procedure_appointment(
            hospital_id, phone, procedure_id, scheduled_at, patient_id=patient_id,
            patient_name=patient_name, patient_age=patient_age, procedure_order_reference=procedure_order_reference,
        )

    def create_procedure_request(self, hospital_id, phone, procedure_id, patient_name=None, patient_age=None, patient_id=None, procedure_order_reference=None):
        return repo.create_procedure_request(
            hospital_id, phone, procedure_id, patient_id=patient_id,
            patient_name=patient_name, patient_age=patient_age, procedure_order_reference=procedure_order_reference,
        )

    def confirm_procedure_appointment(self, hospital_id, appointment_id, scheduled_at):
        return repo.confirm_procedure_appointment(hospital_id, appointment_id, scheduled_at)

    def request_procedure_reschedule(self, hospital_id, appointment_id, requested_at):
        repo.request_procedure_reschedule(hospital_id, appointment_id, requested_at)

    def get_procedure_resources_for_appointment(self, hospital_id, appointment_id):
        return repo.get_procedure_resources_for_appointment(hospital_id, appointment_id)

    def get_pending_procedure_request(self, hospital_id, phone, procedure_id):
        return repo.get_pending_procedure_request(hospital_id, phone, procedure_id)

    def reschedule_booking(self, hospital_id, old_appointment_id, phone, department_id, doctor_id, scheduled_at, patient_id=None, resource_id=None):
        """Books the new slot BEFORE marking the old appointment rescheduled:
        if someone else grabbed this exact doctor+slot first (IntegrityError,
        left to propagate uncaught to the caller — same as create_booking),
        the patient keeps their original appointment rather than being left
        with neither. This ordering is a deliberate Phase 8 fix, now living
        here instead of split across two separate core/booking_flow.py calls.

        Patient identity SEPARATION (Spec.md Section 0): patient_id, when
        given, is threaded straight through to create_appointment() so the
        rebooked slot stays tied to the SAME linked patient the original
        appointment belonged to -- without it, a multi-patient phone
        rescheduling would have no way to know which family member's
        appointment this actually is.

        Appointment type step (WhatsApp flow alignment): the new booking
        inherits the OLD appointment's appointment_type_id -- rescheduling
        changes when a visit happens, not what kind of visit it is, so this
        is read straight off the old row rather than asked again. Any
        consent already given at original booking time does NOT carry
        forward (consent_given_at stays unset on the new row) -- it was
        given for that specific visit, not a standing grant.

        Daycare/Procedure rebuild: a procedure appointment never reaches this
        method at all -- reschedule.py routes it to its own "Request
        Reschedule" flow instead (approval-gated, portal-approved), since an
        instant-booking procedure's resource reservation can't just be
        silently re-pointed at a new slot without re-checking availability
        the same way create_procedure_booking() does. See
        connector.request_procedure_reschedule()/confirm_procedure_appointment().

        Diagnostic/Lab Phase 2: resource_id/diagnostic_test_id/variant/label/
        price all carry forward the same way -- rescheduling moves the slot,
        never re-asks which test/variant was chosen.

        Lab Test Phase 2 follow-up: collection_method/address/pincode/
        home_collection_charge carry forward the same way -- rescheduling
        never re-asks the collection method or basket either. The basket
        itself (a child table, not a column) is copied separately via
        repo.copy_lab_basket() below. lab_status deliberately does NOT carry
        forward as-is -- the new row's own report lifecycle starts fresh at
        'booked' (the sample hasn't been collected for the NEW slot yet),
        the one field here where "unchanged" would be wrong."""
        old_appointment = repo.get_appointment(hospital_id, old_appointment_id)
        new_appointment = repo.create_appointment(
            hospital_id, phone, department_id, doctor_id, scheduled_at, patient_id=patient_id,
            exclude_appointment_id=old_appointment_id,
            appointment_type_id=old_appointment.appointment_type_id if old_appointment else None,
            resource_id=resource_id if resource_id is not None else (old_appointment.resource_id if old_appointment else None),
            diagnostic_test_id=old_appointment.diagnostic_test_id if old_appointment else None,
            diagnostic_test_variant_id=old_appointment.diagnostic_test_variant_id if old_appointment else None,
            diagnostic_test_label=old_appointment.diagnostic_test_label if old_appointment else None,
            diagnostic_variant_label=old_appointment.diagnostic_variant_label if old_appointment else None,
            diagnostic_price=old_appointment.diagnostic_price if old_appointment else None,
            collection_method=old_appointment.collection_method if old_appointment else None,
            collection_address=old_appointment.collection_address if old_appointment else None,
            collection_pincode=old_appointment.collection_pincode if old_appointment else None,
            home_collection_charge=old_appointment.home_collection_charge if old_appointment else None,
            lab_status="booked" if old_appointment and old_appointment.lab_status is not None else None,
        )
        if old_appointment is not None and old_appointment.lab_status is not None:
            repo.copy_lab_basket(hospital_id, old_appointment_id, new_appointment.id)
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

    def get_appointments_in_range(self, hospital_id, care_connect_account_id, range_start, range_end, statuses=None):
        return repo.get_appointments_for_account_in_range(
            hospital_id, care_connect_account_id, range_start, range_end, statuses=statuses,
        )
