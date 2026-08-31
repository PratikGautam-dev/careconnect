# core/logging_config.py
"""Structured (JSON) application logging.

Every module in this app already does `logger = logging.getLogger(__name__)`
and calls .info()/.warning()/etc (core/whatsapp.py, webhook/routes.py,
webhook/dispatch.py, flows/*, reminders/scheduler.py, db/repositories/
platform_settings.py, portal/routes/bookings.py, ...) -- none of them
configure their own handler or formatter, so every one of them propagates up
to the ROOT logger. That means reconfiguring the root logger's handler here
is enough to make every existing log call in the app emit as JSON, with zero
changes to any of those files.

Replaces main.py's old
`logging.basicConfig(level=logging.INFO, format="...")` plain-text line.
Two things this adds beyond that:
  1. JSON output (JSONFormatter) -- one log call is one line of valid JSON,
     so it can be shipped as-is to a log aggregator (Datadog, CloudWatch,
     Better Stack, ...) later with no re-parsing step, while still being
     perfectly readable/greppable by eye locally in dev.
  2. request_id on every log line emitted while handling a given HTTP
     request (core/request_context.py's ContextVar, stamped by main.py's
     _request_logging middleware) -- lets every log line from one incoming
     request be correlated even though the app is handling many requests
     concurrently.

Does NOT touch uvicorn's own "uvicorn"/"uvicorn.error"/"uvicorn.access"
loggers -- per this file's own predecessor comment in main.py, uvicorn
configures those with its own handlers directly, bypassing the root logger
entirely, so its access-log lines will keep printing in uvicorn's own plain
format alongside these JSON lines. main.py's own request-logging middleware
already logs method/path/status/duration in JSON for every request, making
uvicorn's separate access log redundant -- silencing it (uvicorn.run(...,
access_log=False) locally, --no-access-log in the production uvicorn
command) is a reasonable follow-up, not done here to keep this change
contained to logging configuration only."""
import json
import logging
import os
from datetime import datetime, timezone

from core.request_context import get_request_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": get_request_id(),
        }
        # Ad hoc structured fields for a single log call, e.g.
        # logger.info("booking created", extra={"extra_data": {"hospital_id": hospital.id}})
        # -- merged in last so a caller can override any field above
        # (including request_id) for the rare case that's actually correct.
        extra_data = getattr(record, "extra_data", None)
        if extra_data:
            log_obj.update(extra_data)
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # default=str: a caller's extra_data dict may contain something
        # non-JSON-native (a date, a Decimal, an ORM row) -- stringify it
        # rather than letting json.dumps raise and lose the whole log line.
        return json.dumps(log_obj, default=str)


def configure_logging() -> None:
    """Call once, at process startup (main.py) -- sets the ROOT logger's
    handler/formatter/level, which every existing getLogger(__name__) logger
    in this app inherits by propagation, same as the basicConfig() call this
    replaces. LOG_LEVEL is read from the environment (default INFO, matching
    the old basicConfig() call's hardcoded level exactly) so a deployment can
    turn on DEBUG without a code change."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Idempotent: uvicorn's --reload re-executes this module on every code
    # change in dev -- without clearing first, each reload would add ANOTHER
    # handler on top of the last one, and every log line would print twice,
    # then three times, and so on.
    root.handlers.clear()
    root.addHandler(handler)
