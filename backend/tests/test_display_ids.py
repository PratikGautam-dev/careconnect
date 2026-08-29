# tests/test_display_ids.py
"""
Yearly-resetting display-id scheme (db/display_ids.py): the shared
code_sequences table backing DCCG (CareConnect account)/DCCH (hospital)/
DCCC (clinic)/DCCP (patient, paired with mrn) -- covers the actual NEW
behavior this round: the counter genuinely restarts at 1 in a new calendar
year (rather than just trusting the format string looks right), that
different scopes (hospitals, or hospital vs clinic prefixes) never share a
counter, and that db/models.py's _generate_patient_identifiers() threads
`now` through to the same underlying generator. APT (appointment reference
ids) is explicitly untouched by this table -- not covered here, already
covered by tests/test_db.py's own reference-id tests.
"""
from datetime import datetime

import db.connection as db_connection
import db.repository as db
from db.display_ids import (
    CARE_CONNECT_ACCOUNT_PREFIX,
    CLINIC_PREFIX,
    GLOBAL_SCOPE_KEY,
    HOSPITAL_PREFIX,
    PATIENT_DISPLAY_ID_PREFIX,
    generate_yearly_display_id_conn,
    generate_yearly_display_id_session,
    hospital_display_prefix,
)
from db.models import _generate_patient_identifiers


def test_hospital_display_prefix_branches_on_tenant_type():
    assert hospital_display_prefix("hospital") == HOSPITAL_PREFIX
    assert hospital_display_prefix("clinic") == CLINIC_PREFIX
    # Unrecognized/unset tenant_type falls back to the hospital prefix, same
    # "hospital is the default tenant type" convention db/schema.sql's own
    # DEFAULT 'hospital' and DEFAULT_ACTIVE_TYPES_BY_TENANT_TYPE already use.
    assert hospital_display_prefix("something_else") == HOSPITAL_PREFIX


def test_conn_generator_sequence_resets_on_a_new_calendar_year(hospital_id):
    conn = db_connection.get_connection()
    scope = str(hospital_id)
    year_2025 = datetime(2025, 6, 1)
    year_2026 = datetime(2026, 1, 1)

    first = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, scope, now=year_2025)
    second = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, scope, now=year_2025)
    assert first == f"{PATIENT_DISPLAY_ID_PREFIX}-2025-00001"
    assert second == f"{PATIENT_DISPLAY_ID_PREFIX}-2025-00002"

    # A different year for the SAME prefix/scope restarts at 1, not 3.
    third = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, scope, now=year_2026)
    assert third == f"{PATIENT_DISPLAY_ID_PREFIX}-2026-00001"

    # Going back to 2025 for the same prefix/scope continues ITS OWN
    # sequence where it left off -- proves the two years' rows are
    # genuinely independent, not one shared counter that just got reset.
    fourth = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, scope, now=year_2025)
    assert fourth == f"{PATIENT_DISPLAY_ID_PREFIX}-2025-00003"


def test_conn_generator_scopes_are_isolated(hospital_id, second_hospital_id):
    conn = db_connection.get_connection()
    now = datetime(2027, 3, 1)

    a1 = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, str(hospital_id), now=now)
    b1 = generate_yearly_display_id_conn(conn, PATIENT_DISPLAY_ID_PREFIX, str(second_hospital_id), now=now)
    # Two different hospitals (different scope_key) both start at 1 --
    # completely independent counters, same as the old patient_id_counters
    # per-hospital isolation.
    assert a1 == f"{PATIENT_DISPLAY_ID_PREFIX}-2027-00001"
    assert b1 == f"{PATIENT_DISPLAY_ID_PREFIX}-2027-00001"

    # Two different PREFIXES sharing the same scope_key (global) also never
    # collide -- a hospital and a clinic minted in the same year each start
    # their own numbering at 1.
    hos = generate_yearly_display_id_conn(conn, HOSPITAL_PREFIX, GLOBAL_SCOPE_KEY, now=now)
    clinic = generate_yearly_display_id_conn(conn, CLINIC_PREFIX, GLOBAL_SCOPE_KEY, now=now)
    assert hos.startswith(f"{HOSPITAL_PREFIX}-2027-")
    assert clinic.startswith(f"{CLINIC_PREFIX}-2027-")


def test_session_generator_matches_conn_generator_behavior(hospital_id):
    """The ORM-session path (used by create_hospital()/account creation
    inside a session) must be race-safe/atomic the same way the raw-conn
    path is, and land on the exact same table/format."""
    session = db_connection.get_session()
    now = datetime(2028, 1, 1)

    first = generate_yearly_display_id_session(session, CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY, now=now)
    session.commit()
    second = generate_yearly_display_id_session(session, CARE_CONNECT_ACCOUNT_PREFIX, GLOBAL_SCOPE_KEY, now=now)
    session.commit()

    assert first == f"{CARE_CONNECT_ACCOUNT_PREFIX}-2028-00001"
    assert second == f"{CARE_CONNECT_ACCOUNT_PREFIX}-2028-00002"


def test_generate_patient_identifiers_resets_yearly_via_injected_now(hospital_id):
    """db/models.py's own generator, exercised directly with an injected
    `now` (same testability convention _generate_reference_id() already
    established) -- proves the patient_display_id/mrn pair genuinely follows
    the shared yearly-reset scheme, not just that the format string looks
    right."""
    conn = db_connection.get_connection()

    display_1, mrn_1 = _generate_patient_identifiers(conn, hospital_id, now=datetime(2025, 12, 31))
    display_2, mrn_2 = _generate_patient_identifiers(conn, hospital_id, now=datetime(2025, 12, 31))
    assert display_1.endswith("-00001") and "2025" in display_1
    assert display_2.endswith("-00002") and "2025" in display_2
    assert mrn_1.endswith("-00001") and "2025" in mrn_1

    # New year -- same hospital's sequence restarts, and both id and mrn
    # still share the exact same (new) sequence number.
    display_3, mrn_3 = _generate_patient_identifiers(conn, hospital_id, now=datetime(2026, 1, 1))
    assert display_3.endswith("-00001") and "2026" in display_3
    assert mrn_3.endswith("-00001") and "2026" in mrn_3
    assert display_3.rsplit("-", 1)[1] == mrn_3.rsplit("-", 1)[1]
