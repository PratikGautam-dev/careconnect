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

import psycopg2
import psycopg2.extras

# Re-exported so every other module that needs to catch a constraint
# violation (core/booking_flow.py's double-booking race, admin/onboarding.py's
# duplicate phone_number_id) imports it from here rather than knowing which
# driver is underneath — this is the one piece of driver knowledge those
# modules previously had to have directly (as `sqlite3.IntegrityError`).
IntegrityError = psycopg2.IntegrityError

_QUESTION_MARK_RE = re.compile(r"\?")


class _PGConnection:4
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

    def execute(self, sql: str, params=()):
        translated = _QUESTION_MARK_RE.sub("%s", sql)
        if self._conn.closed:
            self._reconnect()
        try:
            cur = self._conn.cursor()
            cur.execute(translated, params)
            return cur
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            # The connection died between our .closed check above and this
            # statement actually running (or was never flagged closed at all,
            # e.g. a Neon-side idle close the client hasn't discovered yet) --
            # reconnect once and retry this exact statement before giving up.
            self._reconnect()
            cur = self._conn.cursor()
            cur.execute(translated, params)
            return cur

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
