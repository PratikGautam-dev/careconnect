# db/repository.py
"""
ARCHITECTURE_PLAN.md Phase 1: this used to be the single ~2900-line data-
access file for every domain (hospitals, users, doctors, leave, slots,
patients, patient records, appointments, dashboard, FAQ, handoffs). Split
into db/models.py (shared dataclasses/exceptions/constants/row-mappers) and
one file per domain under db/repositories/ -- see that plan doc's "Key
restructuring specifics" section for the reasoning.

This module is now a re-export shim so every existing call site
(`import db.repository as db; db.create_appointment(...)`, or
`from db.repository import X`) keeps working unchanged while callers move
to importing db.repositories.<domain> directly over time. Delete this file
once `grep -r "import db.repository"` outside it returns nothing (per the
plan's migration-verification step).
"""
from db.connection import IntegrityError, get_connection

from db.models import *  # noqa: F401,F403
from db.models import (  # noqa: F401 -- db/init_db.py imports these directly
    _generate_patient_identifiers,
    _get_or_create_hospital_short_code,
)

from db.repositories.hospitals import *  # noqa: F401,F403
from db.repositories.users import *  # noqa: F401,F403
from db.repositories.doctors import *  # noqa: F401,F403
from db.repositories.leave import *  # noqa: F401,F403
from db.repositories.slots import *  # noqa: F401,F403
from db.repositories.accounts import *  # noqa: F401,F403
from db.repositories.consent import *  # noqa: F401,F403
from db.repositories.patients import *  # noqa: F401,F403
from db.repositories.patient_records import *  # noqa: F401,F403
from db.repositories.appointment_types import *  # noqa: F401,F403
from db.repositories.daycare_duration_options import *  # noqa: F401,F403
from db.repositories.diagnostic_tests import *  # noqa: F401,F403
from db.repositories.diagnostic_resources import *  # noqa: F401,F403
from db.repositories.resource_slots import *  # noqa: F401,F403
from db.repositories.appointments import *  # noqa: F401,F403
from db.repositories.appointments import _upsert_patient  # noqa: F401 -- some tests import this directly
from db.repositories.dashboard import *  # noqa: F401,F403
from db.repositories.faq import *  # noqa: F401,F403
from db.repositories.handoffs import *  # noqa: F401,F403
from db.repositories.audit_logs import *  # noqa: F401,F403
from db.repositories.platform_settings import *  # noqa: F401,F403
from db.repositories.hospital_settings import *  # noqa: F401,F403
from db.repositories.staff_users import *  # noqa: F401,F403
from db.repositories.role_permissions import *  # noqa: F401,F403
from db.repositories.super_admins import *  # noqa: F401,F403
