from flows.booking import _date_label


def test_date_label_format():
    """Section 12.12: "Sat, Aug 8" style -- weekday abbreviation, comma, month
    abbreviation, day-of-month with NO leading zero (built manually rather
    than via a single strftime directive specifically to sidestep the
    Linux/Windows %-d vs %#d portability split -- see _date_label's own
    docstring)."""
    assert _date_label("2026-08-08") == "Sat, Aug 8"
    assert _date_label("2026-01-01") == "Thu, Jan 1"
    assert _date_label("2026-12-25") == "Fri, Dec 25"
    # Double-digit day -- no leading zero either way, just the real number.
    assert _date_label("2026-08-15") == "Sat, Aug 15"
