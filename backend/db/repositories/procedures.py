# db/repositories/procedures.py
"""Daycare/Procedure rebuild: the procedure catalog a patient picks from
(Step 1), each procedure's booking mode (Step 2), which resource pools it
needs (Step 4), and its pre-procedure instructions (Step 5). Same
"hospital-editable catalog" shape as db/repositories/diagnostic_tests.py."""
from sqlalchemy import select

from db.connection import get_session
from db.orm_models import Procedure, ProcedureInstruction, ProcedureRequiredResourceType

_PROCEDURE_COLUMNS = (
    Procedure.id, Procedure.category, Procedure.name, Procedure.department_id, Procedure.booking_mode,
    Procedure.duration_minutes, Procedure.estimated_price_min, Procedure.estimated_price_max,
    Procedure.is_active, Procedure.sort_order,
)
_INSTRUCTION_COLUMNS = (
    ProcedureInstruction.id, ProcedureInstruction.procedure_id, ProcedureInstruction.instruction_type,
    ProcedureInstruction.instruction_text, ProcedureInstruction.sort_order,
)


def _procedure_dict(row) -> dict:
    d = dict(row._mapping)
    for key in ("estimated_price_min", "estimated_price_max"):
        if d.get(key) is not None:
            d[key] = float(d[key])
    return d


def get_required_resource_types(hospital_id: int, procedure_id: int) -> list[str]:
    session = get_session()
    rows = session.execute(
        select(ProcedureRequiredResourceType.resource_type)
        .where(
            ProcedureRequiredResourceType.hospital_id == hospital_id,
            ProcedureRequiredResourceType.procedure_id == procedure_id,
        )
        .order_by(ProcedureRequiredResourceType.resource_type)
    ).all()
    return [r[0] for r in rows]


def get_instructions_for_procedure(hospital_id: int, procedure_id: int) -> list[dict]:
    session = get_session()
    rows = session.execute(
        select(*_INSTRUCTION_COLUMNS)
        .where(ProcedureInstruction.hospital_id == hospital_id, ProcedureInstruction.procedure_id == procedure_id)
        .order_by(ProcedureInstruction.sort_order, ProcedureInstruction.id)
    ).all()
    return [dict(r._mapping) for r in rows]


def get_procedures(hospital_id: int) -> list[dict]:
    """Active procedures only, each with its required_resource_types and
    instructions nested -- powers the WhatsApp procedure-selection list."""
    session = get_session()
    rows = session.execute(
        select(*_PROCEDURE_COLUMNS)
        .where(Procedure.hospital_id == hospital_id, Procedure.is_active.is_(True))
        .order_by(Procedure.sort_order, Procedure.id)
    ).all()
    procedures = []
    for row in rows:
        p = _procedure_dict(row)
        p["required_resource_types"] = get_required_resource_types(hospital_id, p["id"])
        p["instructions"] = get_instructions_for_procedure(hospital_id, p["id"])
        procedures.append(p)
    return procedures


def get_procedure(hospital_id: int, procedure_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        select(*_PROCEDURE_COLUMNS).where(Procedure.hospital_id == hospital_id, Procedure.id == procedure_id)
    ).first()
    if row is None:
        return None
    p = _procedure_dict(row)
    p["required_resource_types"] = get_required_resource_types(hospital_id, procedure_id)
    p["instructions"] = get_instructions_for_procedure(hospital_id, procedure_id)
    return p


def get_all_procedures_for_hospital(hospital_id: int) -> list[dict]:
    """Active AND inactive, for the portal's own management screen."""
    session = get_session()
    rows = session.execute(
        select(*_PROCEDURE_COLUMNS)
        .where(Procedure.hospital_id == hospital_id)
        .order_by(Procedure.sort_order, Procedure.id)
    ).all()
    procedures = []
    for row in rows:
        p = _procedure_dict(row)
        p["required_resource_types"] = get_required_resource_types(hospital_id, p["id"])
        p["instructions"] = get_instructions_for_procedure(hospital_id, p["id"])
        procedures.append(p)
    return procedures


def create_procedure(
    hospital_id: int, category: str, name: str, booking_mode: str, duration_minutes: int,
    department_id: str | None = None, estimated_price_min: float | None = None,
    estimated_price_max: float | None = None,
) -> dict:
    session = get_session()
    max_sort = session.execute(
        select(Procedure.sort_order).where(Procedure.hospital_id == hospital_id).order_by(Procedure.sort_order.desc())
    ).first()
    sort_order = (max_sort[0] + 1) if max_sort else 0
    row = Procedure(
        hospital_id=hospital_id, category=category, name=name, department_id=department_id,
        booking_mode=booking_mode, duration_minutes=duration_minutes, estimated_price_min=estimated_price_min,
        estimated_price_max=estimated_price_max, is_active=True, sort_order=sort_order,
    )
    session.add(row)
    session.commit()
    return get_procedure(hospital_id, row.id)


def update_procedure(
    hospital_id: int, procedure_id: int, category: str, name: str, booking_mode: str, duration_minutes: int,
    department_id: str | None = None, estimated_price_min: float | None = None,
    estimated_price_max: float | None = None,
) -> dict | None:
    session = get_session()
    from sqlalchemy import update
    result = session.execute(
        update(Procedure)
        .where(Procedure.hospital_id == hospital_id, Procedure.id == procedure_id)
        .values(
            category=category, name=name, department_id=department_id, booking_mode=booking_mode,
            duration_minutes=duration_minutes, estimated_price_min=estimated_price_min,
            estimated_price_max=estimated_price_max,
        )
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_procedure(hospital_id, procedure_id)


def set_procedure_active(hospital_id: int, procedure_id: int, is_active: bool) -> bool:
    from sqlalchemy import update
    session = get_session()
    result = session.execute(
        update(Procedure)
        .where(Procedure.hospital_id == hospital_id, Procedure.id == procedure_id)
        .values(is_active=is_active)
    )
    session.commit()
    return result.rowcount > 0


def delete_procedure(hospital_id: int, procedure_id: int) -> bool:
    from sqlalchemy import delete
    session = get_session()
    session.execute(
        delete(ProcedureRequiredResourceType).where(
            ProcedureRequiredResourceType.hospital_id == hospital_id,
            ProcedureRequiredResourceType.procedure_id == procedure_id,
        )
    )
    session.execute(
        delete(ProcedureInstruction).where(
            ProcedureInstruction.hospital_id == hospital_id, ProcedureInstruction.procedure_id == procedure_id,
        )
    )
    result = session.execute(
        delete(Procedure).where(Procedure.hospital_id == hospital_id, Procedure.id == procedure_id)
    )
    session.commit()
    return result.rowcount > 0


def set_required_resource_types(hospital_id: int, procedure_id: int, resource_types: list[str]) -> None:
    """Replaces the full set in one call -- simpler for the portal's own
    checkbox-group UI than incremental add/remove endpoints."""
    from sqlalchemy import delete
    session = get_session()
    session.execute(
        delete(ProcedureRequiredResourceType).where(
            ProcedureRequiredResourceType.hospital_id == hospital_id,
            ProcedureRequiredResourceType.procedure_id == procedure_id,
        )
    )
    for resource_type in resource_types:
        session.add(ProcedureRequiredResourceType(
            hospital_id=hospital_id, procedure_id=procedure_id, resource_type=resource_type,
        ))
    session.commit()


def create_instruction(hospital_id: int, procedure_id: int, instruction_type: str, instruction_text: str) -> dict:
    session = get_session()
    max_sort = session.execute(
        select(ProcedureInstruction.sort_order)
        .where(ProcedureInstruction.hospital_id == hospital_id, ProcedureInstruction.procedure_id == procedure_id)
        .order_by(ProcedureInstruction.sort_order.desc())
    ).first()
    sort_order = (max_sort[0] + 1) if max_sort else 0
    row = ProcedureInstruction(
        hospital_id=hospital_id, procedure_id=procedure_id, instruction_type=instruction_type,
        instruction_text=instruction_text, sort_order=sort_order,
    )
    session.add(row)
    session.commit()
    return {
        "id": row.id, "procedure_id": procedure_id, "instruction_type": instruction_type,
        "instruction_text": instruction_text, "sort_order": sort_order,
    }


def delete_instruction(hospital_id: int, instruction_id: int) -> bool:
    from sqlalchemy import delete
    session = get_session()
    result = session.execute(
        delete(ProcedureInstruction).where(
            ProcedureInstruction.hospital_id == hospital_id, ProcedureInstruction.id == instruction_id,
        )
    )
    session.commit()
    return result.rowcount > 0
