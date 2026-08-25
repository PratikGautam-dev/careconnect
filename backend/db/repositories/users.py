# db/repositories/users.py
"""Google-OAuth user accounts and hospital-ownership links (Section 15).
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from db.connection import get_connection
from db.models import Hospital, User
from db.repositories.hospitals import _row_to_hospital



def _row_to_user(row) -> User:
    return User(id=row["id"], google_id=row["google_id"], email=row["email"], name=row["name"], created_at=row["created_at"])


def get_user(user_id: int) -> User | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_google_id(google_id: str) -> User | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> User | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_user(row) if row else None


def create_user(email: str, google_id: str | None = None, name: str | None = None) -> User:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO users (google_id, email, name) VALUES (?, ?, ?) RETURNING id",
        (google_id, email, name),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return get_user(new_id)


def set_user_google_id(user_id: int, google_id: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user_id))
    conn.commit()


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
        return get_user(user.id)
    return create_user(email=email, google_id=google_id, name=name)


def link_hospital_owner(hospital_id: int, user_id: int, role: str = "owner") -> None:
    """Idempotent: re-linking an already-owned hospital (e.g. a duplicate
    onboarding submit) is a harmless no-op, not a duplicate row -- same
    reasoning as doctor_leave's UNIQUE(doctor_id, date)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO hospital_users (hospital_id, user_id, role) VALUES (?, ?, ?) "
        "ON CONFLICT (hospital_id, user_id) DO NOTHING",
        (hospital_id, user_id, role),
    )
    conn.commit()


def get_hospitals_for_user(user_id: int) -> list[Hospital]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT h.* FROM hospitals h JOIN hospital_users hu ON hu.hospital_id = h.id "
        "WHERE hu.user_id = ? ORDER BY h.id",
        (user_id,),
    ).fetchall()
    return [_row_to_hospital(r) for r in rows]


def user_owns_hospital(hospital_id: int, user_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM hospital_users WHERE hospital_id = ? AND user_id = ?",
        (hospital_id, user_id),
    ).fetchone()
    return row is not None


def get_owners_for_hospital(hospital_id: int) -> list[User]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT u.* FROM users u JOIN hospital_users hu ON hu.user_id = u.id "
        "WHERE hu.hospital_id = ? ORDER BY u.id",
        (hospital_id,),
    ).fetchall()
    return [_row_to_user(r) for r in rows]


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
    conn = get_connection()
    rows = conn.execute(
        "SELECT u.* FROM users u LEFT JOIN hospital_users hu ON hu.user_id = u.id "
        "WHERE hu.id IS NULL ORDER BY u.created_at DESC",
    ).fetchall()
    return [_row_to_user(r) for r in rows]


