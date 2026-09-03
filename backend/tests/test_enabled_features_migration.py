# tests/test_enabled_features_migration.py
"""
SPEC Section 14.5: the one-time, idempotent flow_type -> enabled_features
backfill (db/init_db.py's _backfill_enabled_features). Covers the exact
mapping for both legacy flow_type values, that it never touches a row that
already has enabled_features set (idempotent / doesn't clobber a tenant's own
later choices), and that the hospital_id fixture's seeded row (created with
schema.sql's flow_type default of 'booking') already reflects this migration
by the time any test sees it -- proving init_db_on_connection() actually runs
the backfill on every startup, not just when explicitly called.
"""
import db.connection as db_connection
import db.repository as db
from db.init_db import _backfill_book_doctor_tests_diagnostics_split, _backfill_enabled_features


def _insert_hospital(conn, name, phone_number_id, flow_type=None, enabled_features=None):
    if flow_type is None:
        cur = conn.execute(
            "INSERT INTO hospitals (name, whatsapp_phone_number_id, enabled_features) "
            "VALUES (?, ?, ?) RETURNING id",
            (name, phone_number_id, enabled_features),
        )
    else:
        cur = conn.execute(
            "INSERT INTO hospitals (name, whatsapp_phone_number_id, flow_type, enabled_features) "
            "VALUES (?, ?, ?, ?) RETURNING id",
            (name, phone_number_id, flow_type, enabled_features),
        )
    conn.commit()
    return cur.fetchone()["id"]


def test_migrated_booking_tenant_gets_old_main_menu_exactly(hospital_id):
    """The old flow_type='booking' main menu had exactly 4 items: Book,
    Reschedule, Cancel, and a static FAQ button (hospital-info text) --
    matched item-for-item by the migration default, no new capability
    silently switched on. WhatsApp menu restructuring: the "booking" feature
    that default lands on is itself further split (by
    _backfill_book_doctor_tests_diagnostics_split, which also runs on every
    startup) into book_doctor_appointment + tests_diagnostics -- by the time
    ANY test sees the hospital_id fixture, both backfills have already run."""
    hospital = db.get_hospital(hospital_id)
    assert hospital.enabled_features == ["book_doctor_appointment", "reschedule", "cancel", "hospital_info", "tests_diagnostics"]


def test_backfill_splits_booking_into_book_doctor_appointment_and_tests_diagnostics(hospital_id):
    """WhatsApp menu restructuring: a hospital whose enabled_features still
    holds the legacy "booking" key (any hospital that hasn't been through
    this backfill yet) ends up with BOTH new keys -- this is a mandatory
    rename+expand of a capability the hospital already had on, unlike
    consent_privacy/manage_language which are new-hospital-only opt-ins."""
    conn = db_connection.get_connection()
    new_id = _insert_hospital(
        conn, "Legacy Split Hospital", "legacy-split-phone", enabled_features='["booking","faq"]',
    )

    _backfill_book_doctor_tests_diagnostics_split(conn)

    assert set(db.get_hospital(new_id).enabled_features) == {"book_doctor_appointment", "tests_diagnostics", "faq"}


def test_backfill_split_is_idempotent(hospital_id):
    conn = db_connection.get_connection()
    new_id = _insert_hospital(
        conn, "Legacy Split Hospital 2", "legacy-split-phone-2", enabled_features='["booking"]',
    )

    _backfill_book_doctor_tests_diagnostics_split(conn)
    _backfill_book_doctor_tests_diagnostics_split(conn)  # run twice -- still idempotent

    assert set(db.get_hospital(new_id).enabled_features) == {"book_doctor_appointment", "tests_diagnostics"}


def test_backfill_split_never_touches_a_hospital_without_booking(hospital_id):
    conn = db_connection.get_connection()
    new_id = _insert_hospital(
        conn, "Faq Only Hospital", "faq-only-phone", enabled_features='["faq"]',
    )

    _backfill_book_doctor_tests_diagnostics_split(conn)

    assert db.get_hospital(new_id).enabled_features == ["faq"]


def test_backfill_maps_booking_flow_type(hospital_id):
    conn = db_connection.get_connection()
    new_id = _insert_hospital(conn, "Legacy Booking Hospital", "legacy-booking-phone", flow_type="booking")

    _backfill_enabled_features(conn)

    assert db.get_hospital(new_id).enabled_features == ["booking", "reschedule", "cancel", "hospital_info"]


def test_backfill_maps_faq_flow_type(hospital_id):
    conn = db_connection.get_connection()
    new_id = _insert_hospital(conn, "Legacy FAQ Hospital", "legacy-faq-phone", flow_type="faq")

    _backfill_enabled_features(conn)

    assert db.get_hospital(new_id).enabled_features == ["faq"]


def test_backfill_is_idempotent_and_never_overwrites_a_manually_set_value(hospital_id):
    """A tenant that already has enabled_features set (either migrated once
    already, or created directly through the new wizard with its own
    selection) must never have that value silently replaced by a later
    startup's backfill run."""
    conn = db_connection.get_connection()
    new_id = _insert_hospital(
        conn, "Custom Tenant", "custom-phone", flow_type="booking", enabled_features='["faq","reports"]',
    )

    _backfill_enabled_features(conn)
    _backfill_enabled_features(conn)  # run twice -- still idempotent

    assert set(db.get_hospital(new_id).enabled_features) == {"faq", "reports"}


def test_backfill_gives_empty_set_for_unrecognized_flow_type(hospital_id):
    conn = db_connection.get_connection()
    new_id = _insert_hospital(conn, "Mystery Tenant", "mystery-phone", flow_type="some_unknown_value")

    _backfill_enabled_features(conn)

    assert db.get_hospital(new_id).enabled_features == []
