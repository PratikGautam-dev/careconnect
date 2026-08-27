# db/repositories/users.py
"""Google-OAuth user accounts and hospital-ownership links (Section 15).
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.connection import get_session
from db.models import Hospital, User
from db.orm_models import HospitalRow, HospitalUser, UserAccount
from db.repositories.hospitals import _HOSPITAL_COLUMNS, _row_to_hospital

_USER_COLUMNS = (UserAccount.id, UserAccount.google_id, UserAccount.email, UserAccount.name, UserAccount.created_at)


def _row_to_user(row) -> User:
    return User(id=row["id"], google_id=row["google_id"], email=row["email"], name=row["name"], created_at=row["created_at"])


def get_user(user_id: int) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(UserAccount.id == user_id)).first()
    return _row_to_user(row._mapping) if row else None


def get_user_by_google_id(google_id: str) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(UserAccount.google_id == google_id)).first()
    return _row_to_user(row._mapping) if row else None


def get_user_by_email(email: str) -> User | None:
    session = get_session()
    row = session.execute(select(*_USER_COLUMNS).where(UserAccount.email == email)).first()
    return _row_to_user(row._mapping) if row else None


def create_user(email: str, google_id: str | None = None, name: str | None = None) -> User:
    session = get_session()
    new_id = session.execute(
        insert(UserAccount).values(google_id=google_id, email=email, name=name).returning(UserAccount.id)
    ).scalar_one()
    session.commit()
    created = get_user(new_id)
    assert created is not None  # the row was just committed above
    return created


def set_user_google_id(user_id: int, google_id: str) -> None:
    session = get_session()
    session.execute(update(UserAccount).where(UserAccount.id == user_id).values(google_id=google_id))
    session.commit()


def get_or_create_user_for_google_login(google_id: str, email: str, name: str | None) -> User:
    """The one lookup rule every Google sign-in goes through (user_auth.py's
    OAuth callback): match an existing google_id first (returning sign-in);
    otherwise match by email (a placeholder row a platform admin pre-created
    via /admin/edit-tenant's owner-assignment field, before this person ever
    signed in with Google) and backfill google_id onto it rather than
    creating a second, disconnected row for the same person; otherwise this
    is a genuinely new identity."""
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


def link_hospital_owner(hospital_id: int, user_id: int, role: str = "owner") -> None:
    """Idempotent: re-linking an already-owned hospital (e.g. a duplicate
    onboarding submit) is a harmless no-op, not a duplicate row -- same
    reasoning as doctor_leave's UNIQUE(doctor_id, date)."""
    session = get_session()
    session.execute(
        pg_insert(HospitalUser)
        .values(hospital_id=hospital_id, user_id=user_id, role=role)
        .on_conflict_do_nothing(index_elements=["hospital_id", "user_id"])
    )
    session.commit()


def get_hospitals_for_user(user_id: int) -> list[Hospital]:
    """Now ORM-based -- hospitals.py's HospitalRow/_HOSPITAL_COLUMNS landed
    with that domain's own migration, closing the deferral this function's
    docstring used to describe."""
    session = get_session()
    rows = session.execute(
        select(*_HOSPITAL_COLUMNS)
        .join(HospitalUser, HospitalUser.hospital_id == HospitalRow.id)
        .where(HospitalUser.user_id == user_id)
        .order_by(HospitalRow.id)
    ).all()
    return [_row_to_hospital(r._mapping) for r in rows]


def user_owns_hospital(hospital_id: int, user_id: int) -> bool:
    session = get_session()
    row = session.execute(
        select(HospitalUser.id).where(HospitalUser.hospital_id == hospital_id, HospitalUser.user_id == user_id)
    ).first()
    return row is not None


def get_owners_for_hospital(hospital_id: int) -> list[User]:
    session = get_session()
    rows = session.execute(
        select(*_USER_COLUMNS)
        .join(HospitalUser, HospitalUser.user_id == UserAccount.id)
        .where(HospitalUser.hospital_id == hospital_id)
        .order_by(UserAccount.id)
    ).all()
    return [_row_to_user(r._mapping) for r in rows]


def assign_hospital_owner_by_email(hospital_id: int, email: str) -> User:
    """admin/tenants_api.py's migration tool (Section 15): a platform admin
    assigns ownership of an already-onboarded hospital (e.g. hospital #1,
    DaaPrime -- onboarded before Google sign-in existed) to a Google account
    by email, without that person needing to have signed in yet. Creates a
    placeholder users row (google_id NULL) if none exists for that email --
    get_or_create_user_for_google_login() finds it by email and backfills
    google_id the first time that person actually signs in with Google."""
    user = get_user_by_email(email)
    if user is None:
        user = create_user(email=email)
    link_hospital_owner(hospital_id, user.id)
    return user


def get_users_without_hospital() -> list[User]:
    """Item 5 (Spec.md Section 0): platform-admin visibility into stalled
    signups -- someone signed in with Google (a real users row exists) but
    never finished onboarding a hospital (no hospital_users row links them
    to one). assign_hospital_owner_by_email() always creates a user AND
    links it in the same call, so this can never accidentally include a
    platform-admin-assigned placeholder -- every row returned here is a
    genuine "signed in, then stopped" case. Most recent first, since that's
    the actionable end for a follow-up."""
    session = get_session()
    rows = session.execute(
        select(*_USER_COLUMNS)
        .join(HospitalUser, HospitalUser.user_id == UserAccount.id, isouter=True)
        .where(HospitalUser.id.is_(None))
        .order_by(UserAccount.created_at.desc())
    ).all()
    return [_row_to_user(r._mapping) for r in rows]


