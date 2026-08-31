# db/repositories/users.py
"""Google-OAuth user accounts and hospital-ownership links (Section 15).

Migration 0016 pointed these at db.orm_models.Identity instead of the
historical UserAccount table. Migration 0018 went further and folded
hospital ownership into StaffDetail (role='admin') instead of a separate
HospitalOwner table -- confirmed with the user, no identity actually owns
more than one hospital in practice, so a dedicated M:M table was pure
redundancy with StaffDetail's own (identity_id, hospital_id, role) shape,
and there is deliberately no separate 'owner' role: a hospital's role
vocabulary is exactly admin/receptionist/doctor, centralized on StaffDetail,
whether the account was created by Google sign-in or by an admin through
the staff-management UI. Every function here keeps its exact name and
signature -- only the underlying tables changed. An OAuth hospital owner is
an Identity with google_id set and a StaffDetail row (role='admin');
password_hash on that Identity may be NULL (Google-only sign-in, no
password-based staff login for that person) -- see
verify_portal_password()'s own None-safe handling. get_users_without_hospital()
below filters on google_id so a staff/super-admin identity created without
ever signing in via Google never gets swept into this OAuth-specific
"stalled signup" list."""
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.models import Hospital, User
from db.orm_models import HospitalRow, Identity, StaffDetail
from db.repositories.hospitals import _HOSPITAL_COLUMNS, _row_to_hospital

_USER_COLUMNS = (Identity.id, Identity.google_id, Identity.email, Identity.name, Identity.created_at)


def _row_to_user(row) -> User:
    return User(id=row["id"], google_id=row["google_id"], email=row["email"], name=row["name"], created_at=row["created_at"])


def get_user(user_id: int) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(Identity.id == user_id)).first()
    return _row_to_user(row._mapping) if row else None


def get_user_by_google_id(google_id: str) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(Identity.google_id == google_id)).first()
    return _row_to_user(row._mapping) if row else None


def get_user_by_email(email: str) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(Identity.email == email)).first()
    return _row_to_user(row._mapping) if row else None


def create_user(email: str, google_id: str | None = None, name: str | None = None) -> User:
    session = get_session()
    new_id = session.execute(
        insert(Identity).values(google_id=google_id, email=email, name=name).returning(Identity.id)
    ).scalar_one()
    session.commit()
    created = get_user(new_id)
    assert created is not None  # the row was just committed above
    return created


def set_user_google_id(user_id: int, google_id: str) -> None:
    session = get_session()
    session.execute(update(Identity).where(Identity.id == user_id).values(google_id=google_id))
    session.commit()


def get_or_create_user_for_google_login(google_id: str, email: str, name: str | None) -> User:
    """The one lookup rule every Google sign-in goes through (user_auth.py's
    OAuth callback): match an existing google_id first (returning sign-in);
    otherwise match by email (a placeholder row a platform admin pre-created
    via /admin/edit-tenant's owner-assignment field, before this person ever
    signed in with Google) and backfill google_id onto it rather than
    creating a second, disconnected row for the same person; otherwise this
    is a genuinely new identity. Since email is now globally unique across
    every principal kind (migration 0016), an email match here could in
    principle land on a staff/super-admin identity with no google_id yet --
    backfilling google_id onto it is still correct (same person, same
    email, now also has an OAuth path in) rather than a bug to guard
    against."""
    user = get_user_by_google_id(google_id)
    if user is not None:
        return user
    user = get_user_by_email(email)
    if user is not None:
        if user.google_id != google_id:
            set_user_google_id(user.id, google_id)
        refreshed = get_user(user.id)
        assert refreshed is not None  # user was just looked up above, still exists
        return refreshed
    return create_user(email=email, google_id=google_id, name=name)


def link_hospital_owner(hospital_id: int, user_id: int, role: str = "admin") -> None:
    """Idempotent: re-linking an already-owned hospital (e.g. a duplicate
    onboarding submit) is a harmless no-op, not a duplicate row -- same
    reasoning as doctor_leave's UNIQUE(doctor_id, date). Writes StaffDetail
    now, not a separate HospitalOwner table (migration 0018) -- identity_id
    is StaffDetail's PK (1:1: one identity, one hospital), so this can only
    ever create ONE row per identity, ever; a second call for a DIFFERENT
    hospital_id on an identity that already has a staff_details row is a
    no-op, not a second link -- consistent with "one identity, one
    hospital", confirmed with the user. role defaults to 'admin', not a
    separate 'owner' value -- confirmed with the user, a hospital's role
    vocabulary stays exactly admin/receptionist/doctor."""
    session = get_session()
    session.execute(
        pg_insert(StaffDetail)
        .values(identity_id=user_id, hospital_id=hospital_id, role=role, doctor_id=None)
        .on_conflict_do_nothing(index_elements=["identity_id"])
    )
    session.commit()


def get_hospitals_for_user(user_id: int) -> list[Hospital]:
    """At most one row now (StaffDetail.identity_id is a 1:1 PK) -- list
    return type kept for caller compatibility (auth/google_oauth.py's
    /api/auth/me), same "preserve the interface, change the table
    underneath" discipline as every other function in this module."""
    session = get_session()
    rows = session.execute(
        select(*_HOSPITAL_COLUMNS)
        .join(StaffDetail, StaffDetail.hospital_id == HospitalRow.id)
        .where(StaffDetail.identity_id == user_id)
        .order_by(HospitalRow.id)
    ).all()
    return [_row_to_hospital(r._mapping) for r in rows]


def user_owns_hospital(hospital_id: int, user_id: int) -> bool:
    session = get_session()
    row = session.execute(
        select(StaffDetail.identity_id).where(
            StaffDetail.hospital_id == hospital_id, StaffDetail.identity_id == user_id
        )
    ).first()
    return row is not None


def get_owners_for_hospital(hospital_id: int) -> list[User]:
    """This hospital's admin-role staff_details identities -- no separate
    'owner' role to filter on (confirmed with the user, centralized on
    'admin'), so this is every admin at the hospital, whether their account
    was created by Google sign-in or by another admin through the
    staff-management UI. admin/tenants_api.py's tenant-detail view uses this
    to show who has admin access to the hospital's portal."""
    session = get_session()
    rows = session.execute(
        select(*_USER_COLUMNS)
        .join(StaffDetail, StaffDetail.identity_id == Identity.id)
        .where(StaffDetail.hospital_id == hospital_id, StaffDetail.role == "admin")
        .order_by(Identity.id)
    ).all()
    return [_row_to_user(r._mapping) for r in rows]


def assign_hospital_owner_by_email(hospital_id: int, email: str) -> User:
    """admin/tenants_api.py's migration tool (Section 15): a platform admin
    assigns ownership of an already-onboarded hospital (e.g. hospital #1,
    DaaPrime -- onboarded before Google sign-in existed) to a Google account
    by email, without that person needing to have signed in yet. Creates a
    placeholder identities row (google_id NULL) if none exists for that
    email -- get_or_create_user_for_google_login() finds it by email and
    backfills google_id the first time that person actually signs in with
    Google."""
    user = get_user_by_email(email)
    if user is None:
        user = create_user(email=email)
    link_hospital_owner(hospital_id, user.id)
    return user


def get_users_without_hospital() -> list[User]:
    """Item 5 (Spec.md Section 0): platform-admin visibility into stalled
    signups -- someone signed in with Google (a real identities row with
    google_id set exists) but never finished onboarding a hospital (no
    staff_details row links them to one, in any role). Filtered to
    google_id IS NOT NULL so a staff/super-admin identity created without
    ever signing in via Google (also, incidentally, hospital-less -- that's
    simply not their context) never appears here.
    assign_hospital_owner_by_email() always creates a user AND links it in
    the same call, so this can never accidentally include a
    platform-admin-assigned placeholder -- every row returned here is a
    genuine "signed in, then stopped" case. Most recent first, since that's
    the actionable end for a follow-up."""
    session = get_session()
    linked = select(StaffDetail.identity_id)
    rows = session.execute(
        select(*_USER_COLUMNS)
        .where(Identity.id.not_in(linked), Identity.google_id.is_not(None))
        .order_by(Identity.created_at.desc())
    ).all()
    return [_row_to_user(r._mapping) for r in rows]
