# core/request_context.py
"""Per-request correlation id, readable from anywhere in the call stack
without threading it through every function signature. contextvars.ContextVar
is task-local under asyncio (FastAPI's actual concurrency model) -- the
async equivalent of thread-local storage -- so two requests being handled
concurrently on the same event loop never see each other's request_id, even
though their code is interleaved. A plain module-level variable or
threading.local() would NOT give that guarantee here, since there's no one
thread per request the way a traditional WSGI app would have."""
import contextvars

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """None outside any request (app startup, a background thread like
    main.py's perms-invalidate subscriber, a script) -- callers/formatters
    must treat that as "no request in progress," not an error."""
    return _request_id.get()


def set_request_id(value: str) -> contextvars.Token:
    """Returns a Token the caller must pass to reset_request_id() once the
    request finishes -- same "set then reset in a finally" contract every
    contextvars.ContextVar user follows, so a value never leaks into
    whatever unrelated code happens to run next on this task/thread."""
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)
