# db/repositories/faq.py
"""FAQ topics -- the faq_flow_type's entire data model (SPEC Section 14.2).
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from db.connection import get_connection

# --- FAQ topics (SPEC Section 14.2, the FAQ flow_type's entire data model) ---

def get_faq_topics(hospital_id: int) -> list[dict]:
    """faq_flow.py's topic menu (Section 14.2) -- ordered by display_order,
    then id as a tiebreaker (display_order isn't unique, ties are expected)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, topic_label, answer_text, display_order FROM faq_topics "
        "WHERE hospital_id = ? ORDER BY display_order, id",
        (hospital_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def find_faq_topic(hospital_id: int, topic_id: str) -> dict | None:
    """topic_id arrives as a WhatsApp interactive-reply id (always a string)
    -- faq_topics.id is a SERIAL int, so a non-numeric/stale/cross-hospital id
    (e.g. a leftover tap from before a flow_type switch) safely resolves to
    "not found" rather than a raw ValueError from the int() conversion."""
    try:
        topic_id_int = int(topic_id)
    except (TypeError, ValueError):
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT id, topic_label, answer_text, display_order FROM faq_topics "
        "WHERE hospital_id = ? AND id = ?",
        (hospital_id, topic_id_int),
    ).fetchone()
    return dict(row) if row else None


def create_faq_topic(
    hospital_id: int, topic_label: str, answer_text: str, display_order: int | None = None,
) -> dict:
    """admin/onboarding.py's wizard Step 7 topic/answer builder (Section 14.3,
    faq-flow tenants only). display_order defaults to "append at the end" of
    this hospital's existing topics, so onboarding-time topics keep the order
    they were entered in without the caller having to compute indices itself."""
    conn = get_connection()
    if display_order is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) + 1 AS next_order FROM faq_topics WHERE hospital_id = ?",
            (hospital_id,),
        ).fetchone()
        display_order = row["next_order"]
    cur = conn.execute(
        "INSERT INTO faq_topics (hospital_id, topic_label, answer_text, display_order) "
        "VALUES (?, ?, ?, ?) RETURNING id",
        (hospital_id, topic_label, answer_text, display_order),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return {"id": new_id, "topic_label": topic_label, "answer_text": answer_text, "display_order": display_order}


