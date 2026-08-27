# db/repositories/faq.py
"""FAQ topics -- the faq_flow_type's entire data model (SPEC Section 14.2).
Split out of db/repository.py -- see ARCHITECTURE_PLAN.md Phase 1."""
from sqlalchemy import func, insert, select

from db.connection import get_session
from db.orm_models import FaqTopic

# --- FAQ topics (SPEC Section 14.2, the FAQ flow_type's entire data model) ---

def get_faq_topics(hospital_id: int) -> list[dict]:
    """faq_flow.py's topic menu (Section 14.2) -- ordered by display_order,
    then id as a tiebreaker (display_order isn't unique, ties are expected)."""
    session = get_session()
    rows = session.execute(
        select(FaqTopic.id, FaqTopic.topic_label, FaqTopic.answer_text, FaqTopic.display_order)
        .where(FaqTopic.hospital_id == hospital_id)
        .order_by(FaqTopic.display_order, FaqTopic.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def find_faq_topic(hospital_id: int, topic_id: str) -> dict | None:
    """topic_id arrives as a WhatsApp interactive-reply id (always a string)
    -- faq_topics.id is a SERIAL int, so a non-numeric/stale/cross-hospital id
    (e.g. a leftover tap from before a flow_type switch) safely resolves to
    "not found" rather than a raw ValueError from the int() conversion."""
    try:
        topic_id_int = int(topic_id)
    except (TypeError, ValueError):
        return None
    session = get_session()
    row = session.execute(
        select(FaqTopic.id, FaqTopic.topic_label, FaqTopic.answer_text, FaqTopic.display_order)
        .where(FaqTopic.hospital_id == hospital_id, FaqTopic.id == topic_id_int)
    ).first()
    return dict(row._mapping) if row else None


def create_faq_topic(
    hospital_id: int, topic_label: str, answer_text: str, display_order: int | None = None,
) -> dict:
    """admin/onboarding.py's wizard Step 7 topic/answer builder (Section 14.3,
    faq-flow tenants only). display_order defaults to "append at the end" of
    this hospital's existing topics, so onboarding-time topics keep the order
    they were entered in without the caller having to compute indices itself."""
    session = get_session()
    if display_order is None:
        display_order = session.execute(
            select(func.coalesce(func.max(FaqTopic.display_order), -1) + 1).where(
                FaqTopic.hospital_id == hospital_id
            )
        ).scalar_one()
    new_id = session.execute(
        insert(FaqTopic)
        .values(
            hospital_id=hospital_id, topic_label=topic_label,
            answer_text=answer_text, display_order=display_order,
        )
        .returning(FaqTopic.id)
    ).scalar_one()
    session.commit()
    return {"id": new_id, "topic_label": topic_label, "answer_text": answer_text, "display_order": display_order}


