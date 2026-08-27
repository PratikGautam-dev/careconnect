# db/connection.py
"""
Thin connection layer — the only place that knows this is Postgres (SPEC
Section 6/12.6: moved off SQLite before real production load, onto Neon).
Swapping the backend again later means changing this file and db/schema.sql,
not touching db/repository.py's callers (core/booking_flow.py,
reminders/scheduler.py, slots/scheduler.py) — those only ever call
get_connection() and use the connection's .execute()/.commit() methods.

_PGConnection below is a thin adapter, not a different database abstraction:
it exists purely so db/repository.py's existing conn.execute(sql, params)
.fetchone()/.fetchall() call sites (written against sqlite3.Connection's
chainable-cursor convenience method) keep working unchanged against psycopg2,
which has no such method on the connection object itself. It also rewrites
the `?` placeholders repository.py already uses into psycopg2's `%s` style,
so that conversion didn't have to touch every call site individually.

psycopg2 (sync) was chosen over asyncpg specifically because every
db/repository.py function is already plain sync code called directly from
async FastAPI handlers (blocking the event loop each call, same as the old
sqlite3 driver did) — switching to asyncpg would mean async-ifying every
repository function and every caller, a far bigger change than "swap the
database backend."

A single module-level connection is reused for the process lifetime. Neon
(serverless Postgres) closes idle connections server-side after a period of
inactivity, so _PGConnection transparently detects and reconnects around
that (see execute()/_ensure_connected() below) rather than the app crashing
on the next query after a quiet spell. Tests swap it out via set_connection()
to point at a real (testcontainers-provisioned) Postgres instance whose
schema gets reset between tests — see tests/conftest.py.

Recommendation (not implemented here): a single persistent connection is
adequate for this app's current traffic and is what the detect-and-reconnect
fix below targets, but it's a stopgap, not the ideal end state for a
serverless-Postgres backend. Neon's own pooled connection string (the
"-pooler" host, already what most Neon connection strings default to) or a
proper client-side pool (psycopg2.pool.ThreadedConnectionPool, or an
external pgbouncer) would avoid single-point-of-failure reconnect latency
entirely and handle concurrent requests better once traffic grows beyond
what one connection can serialize through. Worth revisiting before this
app has enough concurrent load that connection-per-request contention (or
this module's reconnect-on-failure retry) becomes a bottleneck.
"""
import os
import re
from typing import Any, NoReturn, Protocol, cast

import psycopg2
import psycopg2.extras
import sqlalchemy.exc
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class _Row(Protocol):
    """A RealDictCursor row: dict-like access by column name."""
    def __getitem__(self, key: str) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...


class _Cursor(Protocol):
    """What repository code actually calls on an execute() result. The real
    object is a psycopg2 RealDictCursor -- rows come back dict-like despite
    psycopg2's own stubs describing plain tuples, so execute() casts to this
    Protocol rather than fighting those stubs."""
    @property
    def rowcount(self) -> int: ...
    def fetchone(self) -> _Row | None: ...
    def fetchall(self) -> list[_Row]: ...

# Re-exported so every other module that needs to catch a constraint
# violation (core/booking_flow.py's double-booking race, admin/onboarding.py's
# duplicate phone_number_id) imports it from here rather than knowing which
# driver is underneath — this is the one piece of driver knowledge those
# modules previously had to have directly (as `sqlite3.IntegrityError`).
IntegrityError = psycopg2.IntegrityError

_QUESTION_MARK_RE = re.compile(r"\?")


class _PGConnection:
    """Wraps a psycopg2 connection to give it sqlite3.Connection's
    conn.execute(sql, params).fetchone()/.fetchall() chaining convenience,
    dict-like row access (via RealDictCursor), and an executescript() for
    running db/schema.sql's multi-statement script in one call.

    Also resilient to Neon closing this connection server-side after a period
    of inactivity: execute()/executescript() check for an already-known-closed
    connection before running a statement, AND catch psycopg2.InterfaceError/
    OperationalError from the statement itself and retry once against a fresh
    connection -- the pre-check alone isn't enough, because psycopg2's
    .closed attribute only reflects a connection the client has already tried
    (and failed) to use; a connection Neon just silently dropped still reports
    .closed == 0 until the next query actually hits the dead socket. Only one
    retry is attempted -- a second consecutive failure is a real problem
    (Neon down, bad DSN, etc.), not another idle-timeout, and should surface
    as an error rather than retry forever."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn = self._new_raw_connection()

    def _new_raw_connection(self):
        conn = psycopg2.connect(self._dsn, cursor_factory=psycopg2.extras.RealDictCursor)
        # Critical behavioral difference from SQLite: Postgres aborts the
        # *entire* transaction after any failed statement (e.g. the
        # IntegrityError core/booking_flow.py's double-booking race and
        # admin/onboarding.py's duplicate-phone_number_id catch are built
        # around) -- every subsequent statement on that connection would raise
        # "current transaction is aborted" until a ROLLBACK, even unrelated
        # SELECTs, unless autocommit is on. Autocommit makes each statement its
        # own implicitly-committed transaction, so a caught IntegrityError
        # doesn't poison anything after it -- matching how SQLite (and this
        # codebase's existing "execute, then explicitly .commit()" pattern,
        # never spanning a transaction across multiple repository calls)
        # already behaved.
        conn.autocommit = True
        return conn

    def _reconnect(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass  # already broken/closed -- nothing to clean up
        self._conn = self._new_raw_connection()

    def execute(self, sql: str, params=()) -> _Cursor:
        translated = _QUESTION_MARK_RE.sub("%s", sql)
        if self._conn.closed:
            self._reconnect()
        try:
            cur = self._conn.cursor()
            cur.execute(translated, params)
            return cast(_Cursor, cur)
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            # The connection died between our .closed check above and this
            # statement actually running (or was never flagged closed at all,
            # e.g. a Neon-side idle close the client hasn't discovered yet) --
            # reconnect once and retry this exact statement before giving up.
            self._reconnect()
            cur = self._conn.cursor()
            cur.execute(translated, params)
            return cast(_Cursor, cur)

    def executescript(self, sql: str) -> None:
        if self._conn.closed:
            self._reconnect()
        try:
            self._conn.cursor().execute(sql)
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            self._reconnect()
            self._conn.cursor().execute(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


_connection: _PGConnection | None = None


def get_database_url() -> str:
    """No sensible default exists for Postgres the way a local SQLite file
    path used to have one — Neon (or any Postgres) always requires an
    explicit connection string, so this raises rather than silently falling
    back to something that would just fail later with a worse error."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required (e.g. the connection "
            "string Neon gives you for this database) — there is no default now "
            "that SQLite has been replaced with Postgres."
        )
    return url


def _connect(dsn: str) -> _PGConnection:
    return _PGConnection(dsn)


def get_connection() -> _PGConnection:
    global _connection
    if _connection is None:
        _connection = _connect(get_database_url())
    return _connection


def set_connection(conn) -> None:
    """Test hook: point every repository function at a specific (e.g.
    testcontainers-provisioned) connection."""
    global _connection
    _connection = conn


def reset_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
    _connection = None


# --- SQLAlchemy engine/session (ORM migration groundwork) ---
#
# Deliberately additive, not a replacement: _PGConnection/get_connection()
# above stay the live path for every db/repositories/*.py function until
# that domain's own migration converts it to use get_session() instead (one
# domain PR at a time, per the SQLAlchemy ORM + Alembic migration plan) --
# ripping out _PGConnection now would break all 14 repository files at once,
# not just the ones actually being migrated. IntegrityError above is
# similarly left as psycopg2.IntegrityError for now; each domain's own
# migration PR decides whether its `except IntegrityError:` call sites need
# to also catch sqlalchemy.exc.IntegrityError once that domain uses
# get_session() instead of get_connection().

_engine: Engine | None = None
_session: Session | None = None


def get_engine() -> Engine:
    """SQLAlchemy Engine for the same DATABASE_URL get_connection() uses.
    pool_pre_ping=True is SQLAlchemy's built-in equivalent of _PGConnection's
    hand-rolled Neon-idle-disconnect detect-and-reconnect logic above (it
    checks a pooled connection is still alive before handing it out) -- ORM-
    based repository code doesn't need to reimplement that workaround.

    isolation_level="AUTOCOMMIT" matches _PGConnection.__init__'s own
    `conn.autocommit = True` exactly (same underlying psycopg2 mechanism) --
    load-bearing, not cosmetic: get_session() below returns ONE Session
    object reused for the process lifetime, same shape as get_connection()'s
    single reused connection. Without autocommit, a failed statement (e.g. a
    UNIQUE-constraint IntegrityError an ORM-migrated repository function
    lets propagate to its caller, same as the old code did) leaves Postgres's
    transaction "aborted" on that shared session -- poisoning every
    subsequent statement ANY caller runs on it afterward with "current
    transaction is aborted", not just the one that failed. Autocommit makes
    each statement its own implicitly-committed unit exactly like
    _PGConnection already documents doing for the raw-SQL path, so a caught
    exception here doesn't poison anything after it either -- verified via a
    real UNIQUE-violation test, not assumed (see the hospitals.py domain's
    migration notes)."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    return _engine


def get_session() -> Session:
    """SQLAlchemy Session, mirroring get_connection()'s shape: one object
    reused for the process lifetime (not a session-per-request pattern), so
    ORM-based repository code added by a future domain migration calls
    session.commit() explicitly at the same points conn.commit() is called
    today, rather than adopting a different transaction-lifecycle model.
    Nothing reads through this yet -- see the module-level comment above."""
    global _session
    if _session is None:
        _session = sessionmaker(bind=get_engine())()
    return _session


def set_session(session: Session) -> None:
    """Test hook counterpart to set_connection() above."""
    global _session
    _session = session


def reset_session() -> None:
    global _session
    if _session is not None:
        _session.close()
    _session = None


def reraise_as_driver_integrity_error(sa_error: sqlalchemy.exc.IntegrityError) -> NoReturn:
    """SQLAlchemy wraps a real constraint violation (e.g. a UNIQUE-index hit)
    in its own sqlalchemy.exc.IntegrityError, with the original driver
    exception on `.orig` -- but every existing `except IntegrityError:` call
    site in this app (admin/onboarding_api.py, admin/tenants_api.py, and
    core/booking_flow.py's double-booking handling once appointments.py
    migrates) was written against IntegrityError above (psycopg2's), from
    when every write went through _PGConnection directly. An ORM-migrated
    repository function whose caller relies on catching that specific type
    calls this in its `except sqlalchemy.exc.IntegrityError:` handler to
    re-raise the ORIGINAL driver exception instead, so those call sites keep
    working unchanged. Never call this for an exception no caller catches by
    type -- letting sqlalchemy.exc.IntegrityError propagate as-is is fine
    there."""
    if isinstance(sa_error.orig, IntegrityError):
        raise sa_error.orig from sa_error
    raise sa_error
