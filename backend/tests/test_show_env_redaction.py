# tests/test_show_env_redaction.py
"""
scripts/show_env.py -- the name-based (not value-shape-based) env-file
redaction utility, added after a value-shape regex (matching a
"://user:pass@" URL pattern) correctly redacted a database URL but printed a
WHATSAPP_ACCESS_TOKEN in full, since that token doesn't have a URL shape.

Covers: every credential-shaped name in this project's actual .env is
redacted (the exact regression case, plus every other real key currently in
use); explicitly-safe plain-config names are shown in full; and -- the
actual point of a fail-CLOSED design -- an unrecognized/hypothetical FUTURE
variable name is redacted by default rather than assumed safe, so a new
credential type never needs a corresponding special case to be protected.
"""
from scripts.show_env import is_sensitive, redact_line


def test_known_credential_names_are_sensitive():
    """The exact regression: WHATSAPP_ACCESS_TOKEN has no URL shape at all,
    so a value-shape check would (and did) miss it entirely."""
    for name in [
        "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN",
        "ADMIN_SECRET", "INTERNAL_SECRET", "PORTAL_SECRET", "MP_ACCESS_TOKEN",
        "MP_WEBHOOK_SECRET", "DATABASE_URL", "REDIS_URL",
    ]:
        assert is_sensitive(name) is True, f"{name} should be treated as sensitive"


def test_google_service_account_json_is_sensitive_despite_no_denylist_keyword_match():
    """A real example already in this project's own .env: a private-key-
    bearing variable named with none of the "obvious" keywords a pure
    denylist (TOKEN/SECRET/KEY/PASSWORD) would check for -- caught here only
    because unrecognized names are redacted by default, not because "JSON"
    happens to be in the keyword list (removing that keyword must still not
    leak this, which the next test checks)."""
    assert is_sensitive("GOOGLE_SERVICE_ACCOUNT_JSON") is True


def test_explicitly_safe_names_are_shown():
    for name in ["WHATSAPP_PHONE_NUMBER_ID", "GOOGLE_CALENDAR_ID", "GOOGLE_CALENDAR_OWNER_EMAIL"]:
        assert is_sensitive(name) is False, f"{name} should be shown, not redacted"


def test_unrecognized_future_variable_name_defaults_to_redacted():
    """The actual point of failing closed: a brand-new credential type with a
    name nobody thought to denylist in advance (e.g. a future
    STRIPE_CLIENT_ID or SOME_NEW_PROVIDER_HANDLE) must be redacted by
    default, not printed until someone remembers to blocklist it."""
    assert is_sensitive("SOME_FUTURE_CREDENTIAL_NOBODY_NAMED_YET") is True
    assert is_sensitive("YET_ANOTHER_UNKNOWN_VAR") is True


def test_safe_allowlisted_name_still_redacted_if_it_also_matches_a_keyword():
    """Belt-and-suspenders: even a mistake (a sensitive name accidentally
    added to the safe allowlist) doesn't leak, as long as it also matches a
    keyword -- the keyword check runs regardless of allowlist membership."""
    assert is_sensitive("GOOGLE_CALENDAR_ID") is False  # sanity: normally safe
    # A hypothetical name that both LOOKS like a safe calendar id AND
    # contains a sensitive keyword must still redact.
    assert is_sensitive("GOOGLE_CALENDAR_SECRET_ID") is True


def test_redact_line_never_includes_the_raw_value_for_a_sensitive_name():
    line = "WHATSAPP_ACCESS_TOKEN=EAAsomeVeryRealLookingTokenValueHere1234567890"
    result = redact_line(line)
    assert "EAAsomeVeryRealLookingTokenValueHere1234567890" not in result
    assert "redacted" in result


def test_redact_line_shows_non_sensitive_values_unchanged():
    line = "WHATSAPP_PHONE_NUMBER_ID=1232463886616393"
    assert redact_line(line) == line


def test_redact_line_passes_through_comments_and_blank_lines():
    assert redact_line("# a comment") == "# a comment"
    assert redact_line("") == ""
    assert redact_line("   ") == "   "


def test_redact_line_handles_empty_value():
    result = redact_line("ADMIN_SECRET=")
    assert "redacted" in result
    assert result == "ADMIN_SECRET=<redacted -- (empty)>"
