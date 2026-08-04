#!/usr/bin/env python3
"""
Safely preview a .env-style file's variables without ever printing a
sensitive value in full.

Why this exists: an earlier ad hoc redaction attempt (a one-off shell regex
matching a "://user:pass@" URL shape) correctly masked a database URL but
printed a WHATSAPP_ACCESS_TOKEN in full, because that token doesn't have a
URL shape -- the redaction was guessing at what a secret LOOKS like, and
missed a format it hadn't anticipated.

This redacts by VARIABLE NAME instead, and fails CLOSED: every name is
treated as sensitive UNLESS it's explicitly listed in _SAFE_NAMES below, not
the other way around. A keyword denylist (redact anything containing TOKEN/
SECRET/KEY/PASSWORD/...) was considered and rejected as the primary
mechanism -- it still requires anticipating every sensitive-sounding word in
advance, and GOOGLE_SERVICE_ACCOUNT_JSON (a private key, but named with none
of those words) is a real example in this project's own .env that a pure
keyword denylist would miss. _SENSITIVE_KEYWORDS below is kept only as an
extra belt-and-suspenders check on top of the allowlist, not the primary
defense: even a name mistakenly added to _SAFE_NAMES still gets redacted if
it also matches a sensitive keyword.

Usage:
    python scripts/show_env.py            # previews .env in the cwd
    python scripts/show_env.py .env.production
"""
import re
import sys
from pathlib import Path

# Names explicitly known to be non-sensitive (plain IDs/config, not
# credentials). Everything NOT in this set is redacted by default,
# regardless of whether its name "looks" sensitive -- fail closed.
_SAFE_NAMES = {
    "WHATSAPP_PHONE_NUMBER_ID",
    "GOOGLE_CALENDAR_ID",
    "GOOGLE_CALENDAR_OWNER_EMAIL",
    "HOSPITAL_NAME",
    "PORT",
    "ENV",
    "ENVIRONMENT",
}

# Extra safety net, not the primary mechanism (see module docstring): a name
# matching any of these is redacted even if it's also in _SAFE_NAMES.
_SENSITIVE_KEYWORDS = re.compile(
    r"(TOKEN|SECRET|KEY|PASSWORD|PWD|CREDENTIAL|AUTH|URL|DSN|CONNECTION|JSON|CERT|PRIVATE)",
    re.IGNORECASE,
)


def is_sensitive(name: str) -> bool:
    if _SENSITIVE_KEYWORDS.search(name):
        return True
    return name not in _SAFE_NAMES


def redact_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return line.rstrip("\n")
    name, _, value = stripped.partition("=")
    name = name.strip()
    if is_sensitive(name):
        shown = "(empty)" if not value.strip() else f"set, {len(value)} chars"
        return f"{name}=<redacted -- {shown}>"
    return f"{name}={value}"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".env")
    if not path.exists():
        print(f"{path} not found", file=sys.stderr)
        sys.exit(1)
    for line in path.read_text(encoding="utf-8").splitlines():
        print(redact_line(line))


if __name__ == "__main__":
    main()
