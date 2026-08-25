from flows.common import cap_rows, is_reset_keyword


def _text(s):
    return {"type": "text", "text": s}


def _tap(option_id):
    return {"type": "interactive_reply", "id": option_id, "title": ""}


# --- Reset keywords (English + Hindi) ---

def test_english_reset_keywords_recognized():
    for word in ["hi", "hello", "hey", "menu", "start", "restart"]:
        assert is_reset_keyword(_text(word))
        assert is_reset_keyword(_text(word.upper()))
        assert is_reset_keyword(_text(f"  {word}  "))  # surrounding whitespace


def test_hindi_reset_keywords_recognized():
    for word in ["नमस्ते", "हाय", "मेनू", "शुरू", "रीस्टार्ट"]:
        assert is_reset_keyword(_text(word))
        assert is_reset_keyword(_text(f"  {word}  "))


def test_non_reset_text_not_recognized():
    assert not is_reset_keyword(_text("cardiology please"))
    assert not is_reset_keyword(_text("नमस्ते ji"))  # not an exact match


def test_interactive_reply_never_treated_as_reset_keyword():
    # Even if a tapped option's id/title happened to collide with a reset
    # word, only free-text messages are eligible -- a button/list tap is
    # always a deliberate selection, never a reset.
    assert not is_reset_keyword(_tap("menu"))


# --- cap_rows (Meta's 10-row WhatsApp list limit) ---

def test_cap_rows_leaves_short_lists_untouched():
    rows = [{"id": str(i)} for i in range(5)]
    assert cap_rows(rows, "test") == rows


def test_cap_rows_truncates_to_ten():
    rows = [{"id": str(i)} for i in range(15)]
    capped = cap_rows(rows, "test")
    assert len(capped) == 10
    assert capped == rows[:10]
