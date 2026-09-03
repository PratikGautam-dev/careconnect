# db/repositories/diagnostic_tests.py
"""Diagnostic/Lab Phase 2 (docs/per-appointment-type-flow-plan.md Step 5):
the test catalog a patient picks from (Diagnostic Test / Lab Test menus),
plus its variants. Same "hospital-editable catalog" shape as
db/repositories/daycare_duration_options.py -- a hospital can freely
add/relabel/remove its own tests and variants, unlike the fixed
appointment_types catalog."""
from sqlalchemy import delete, select, update

from db.connection import get_session
from db.orm_models import DiagnosticTest, DiagnosticTestVariant

CATEGORY_DIAGNOSTIC = "diagnostic"
CATEGORY_LAB = "lab"

# Seeded once per hospital at onboarding/backfill (db/init_db.py), one
# default "Standard" variant each -- a starting point every hospital can
# freely relabel/reprice/add-to/remove afterwards via the portal.
DEFAULT_DIAGNOSTIC_TESTS = (
    "MRI", "CT Scan", "X-Ray", "Ultrasound", "ECG", "Echocardiography", "Mammography", "Other Diagnostic Test",
)
DEFAULT_LAB_TESTS = (
    "CBC", "LFT", "KFT", "Lipid Profile", "Thyroid Profile", "Urine Routine", "Other Lab Test",
)

_TEST_COLUMNS = (
    DiagnosticTest.id, DiagnosticTest.category, DiagnosticTest.name, DiagnosticTest.resource_id,
    DiagnosticTest.is_active, DiagnosticTest.sort_order,
)
_VARIANT_COLUMNS = (
    DiagnosticTestVariant.id, DiagnosticTestVariant.test_id, DiagnosticTestVariant.label,
    DiagnosticTestVariant.price, DiagnosticTestVariant.preparation_instructions,
    DiagnosticTestVariant.is_active, DiagnosticTestVariant.sort_order,
)


def _variant_dict(row) -> dict:
    d = dict(row._mapping)
    if d.get("price") is not None:
        d["price"] = float(d["price"])
    return d


def get_diagnostic_tests(hospital_id: int, category: str) -> list[dict]:
    """Active tests only, each with its active variants nested under
    "variants" -- powers the WhatsApp test-selection list. A test with zero
    active variants is excluded entirely (nothing bookable under it)."""
    session = get_session()
    test_rows = session.execute(
        select(*_TEST_COLUMNS)
        .where(
            DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.category == category,
            DiagnosticTest.is_active.is_(True),
        )
        .order_by(DiagnosticTest.sort_order, DiagnosticTest.id)
    ).all()
    tests = []
    for row in test_rows:
        test = dict(row._mapping)
        variants = get_variants_for_test(hospital_id, test["id"])
        if not variants:
            continue
        test["variants"] = variants
        tests.append(test)
    return tests


def get_variants_for_test(hospital_id: int, test_id: int) -> list[dict]:
    """Active variants only, in display order."""
    session = get_session()
    rows = session.execute(
        select(*_VARIANT_COLUMNS)
        .where(
            DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.test_id == test_id,
            DiagnosticTestVariant.is_active.is_(True),
        )
        .order_by(DiagnosticTestVariant.sort_order, DiagnosticTestVariant.id)
    ).all()
    return [_variant_dict(r) for r in rows]


def get_diagnostic_test(hospital_id: int, test_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        select(*_TEST_COLUMNS).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    ).first()
    return dict(row._mapping) if row else None


def get_variant(hospital_id: int, variant_id: int) -> dict | None:
    session = get_session()
    row = session.execute(
        select(*_VARIANT_COLUMNS)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.id == variant_id)
    ).first()
    return _variant_dict(row) if row else None


def get_all_diagnostic_tests_for_hospital(hospital_id: int, category: str | None = None) -> list[dict]:
    """Active AND inactive tests (with ALL their variants, active or not),
    for the portal's own management screen."""
    session = get_session()
    stmt = select(*_TEST_COLUMNS).where(DiagnosticTest.hospital_id == hospital_id)
    if category is not None:
        stmt = stmt.where(DiagnosticTest.category == category)
    test_rows = session.execute(stmt.order_by(DiagnosticTest.sort_order, DiagnosticTest.id)).all()
    tests = []
    for row in test_rows:
        test = dict(row._mapping)
        variant_rows = session.execute(
            select(*_VARIANT_COLUMNS)
            .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.test_id == test["id"])
            .order_by(DiagnosticTestVariant.sort_order, DiagnosticTestVariant.id)
        ).all()
        test["variants"] = [_variant_dict(r) for r in variant_rows]
        tests.append(test)
    return tests


def create_diagnostic_test(hospital_id: int, category: str, name: str, resource_id: str | None = None) -> dict:
    session = get_session()
    max_sort_order = session.execute(
        select(DiagnosticTest.sort_order)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.category == category)
        .order_by(DiagnosticTest.sort_order.desc()).limit(1)
    ).scalar()
    test = DiagnosticTest(
        hospital_id=hospital_id, category=category, name=name, resource_id=resource_id, is_active=True,
        sort_order=(max_sort_order + 1) if max_sort_order is not None else 0,
    )
    session.add(test)
    session.commit()
    return {
        "id": test.id, "category": test.category, "name": test.name, "resource_id": test.resource_id,
        "is_active": test.is_active, "sort_order": test.sort_order,
    }


def update_diagnostic_test(hospital_id: int, test_id: int, name: str, resource_id: str | None) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DiagnosticTest)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
        .values(name=name, resource_id=resource_id)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_diagnostic_test(hospital_id, test_id)


def set_diagnostic_test_active(hospital_id: int, test_id: int, is_active: bool) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DiagnosticTest)
        .where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
        .values(is_active=is_active)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_diagnostic_test(hospital_id, test_id)


def delete_diagnostic_test(hospital_id: int, test_id: int) -> bool:
    """Cascades to its own variants -- a test can't meaningfully exist
    without them, and nothing else references a variant row."""
    session = get_session()
    session.execute(
        delete(DiagnosticTestVariant)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.test_id == test_id)
    )
    result = session.execute(
        delete(DiagnosticTest).where(DiagnosticTest.hospital_id == hospital_id, DiagnosticTest.id == test_id)
    )
    session.commit()
    return result.rowcount > 0


def create_variant(
    hospital_id: int, test_id: int, label: str, price: float | None, preparation_instructions: str | None,
) -> dict:
    session = get_session()
    max_sort_order = session.execute(
        select(DiagnosticTestVariant.sort_order)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.test_id == test_id)
        .order_by(DiagnosticTestVariant.sort_order.desc()).limit(1)
    ).scalar()
    variant = DiagnosticTestVariant(
        hospital_id=hospital_id, test_id=test_id, label=label, price=price,
        preparation_instructions=preparation_instructions, is_active=True,
        sort_order=(max_sort_order + 1) if max_sort_order is not None else 0,
    )
    session.add(variant)
    session.commit()
    return _variant_dict_from_model(variant)


def _variant_dict_from_model(variant: DiagnosticTestVariant) -> dict:
    return {
        "id": variant.id, "test_id": variant.test_id, "label": variant.label,
        "price": float(variant.price) if variant.price is not None else None,
        "preparation_instructions": variant.preparation_instructions,
        "is_active": variant.is_active, "sort_order": variant.sort_order,
    }


def update_variant(
    hospital_id: int, variant_id: int, label: str, price: float | None, preparation_instructions: str | None,
) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DiagnosticTestVariant)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.id == variant_id)
        .values(label=label, price=price, preparation_instructions=preparation_instructions)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_variant(hospital_id, variant_id)


def set_variant_active(hospital_id: int, variant_id: int, is_active: bool) -> dict | None:
    session = get_session()
    result = session.execute(
        update(DiagnosticTestVariant)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.id == variant_id)
        .values(is_active=is_active)
    )
    session.commit()
    if result.rowcount == 0:
        return None
    return get_variant(hospital_id, variant_id)


def delete_variant(hospital_id: int, variant_id: int) -> bool:
    session = get_session()
    result = session.execute(
        delete(DiagnosticTestVariant)
        .where(DiagnosticTestVariant.hospital_id == hospital_id, DiagnosticTestVariant.id == variant_id)
    )
    session.commit()
    return result.rowcount > 0
