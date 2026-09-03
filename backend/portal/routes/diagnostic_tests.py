# portal/routes/diagnostic_tests.py
"""Portal CRUD for diagnostic_tests/diagnostic_test_variants (Diagnostic/Lab
Phase 2, docs/per-appointment-type-flow-plan.md Step 5) -- same "hospital-
editable catalog" shape as daycare_duration_options.py, reusing the
manage_appointment_types capability (same portal screen area)."""
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

import db.repository as db
from portal.deps import _authenticate, require_capability

router = APIRouter()

_VALID_CATEGORIES = {"diagnostic", "lab"}


@router.get("/api/portal/diagnostic-tests")
async def portal_diagnostic_tests(category: str | None = None, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    return JSONResponse({"tests": db.get_all_diagnostic_tests_for_hospital(hospital.id, category=category)})


@router.post("/api/portal/diagnostic-tests")
async def portal_create_diagnostic_test(payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    category = (payload or {}).get("category") or ""
    name = ((payload or {}).get("name") or "").strip()
    resource_id = (payload or {}).get("resource_id") or None
    if category not in _VALID_CATEGORIES or not name:
        return JSONResponse({"error": "category ('diagnostic'/'lab') and name are required."}, status_code=400)
    if resource_id and db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "Choose a valid resource."}, status_code=400)
    test = db.create_diagnostic_test(hospital.id, category, name, resource_id=resource_id)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.create",
        entity_type="diagnostic_test", entity_id=str(test["id"]), after=test,
    )
    return JSONResponse({"test": test})


@router.put("/api/portal/diagnostic-tests/{test_id}")
async def portal_update_diagnostic_test(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    name = ((payload or {}).get("name") or "").strip()
    resource_id = (payload or {}).get("resource_id") or None
    if not name:
        return JSONResponse({"error": "name is required."}, status_code=400)
    if resource_id and db.get_resource_full(hospital.id, resource_id) is None:
        return JSONResponse({"error": "Choose a valid resource."}, status_code=400)
    updated = db.update_diagnostic_test(hospital.id, test_id, name, resource_id)
    if updated is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.update",
        entity_type="diagnostic_test", entity_id=str(test_id), after=updated,
    )
    return JSONResponse({"test": updated})


@router.post("/api/portal/diagnostic-tests/{test_id}/active")
async def portal_set_diagnostic_test_active(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_diagnostic_test_active(hospital.id, test_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.toggle",
        entity_type="diagnostic_test", entity_id=str(test_id), after={"is_active": is_active},
    )
    return JSONResponse({"test": updated})


@router.delete("/api/portal/diagnostic-tests/{test_id}")
async def portal_delete_diagnostic_test(test_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    deleted = db.delete_diagnostic_test(hospital.id, test_id)
    if not deleted:
        return JSONResponse({"error": "No such test."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test.delete",
        entity_type="diagnostic_test", entity_id=str(test_id),
    )
    return JSONResponse({"deleted": True})


@router.post("/api/portal/diagnostic-tests/{test_id}/variants")
async def portal_create_variant(test_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    if db.get_diagnostic_test(hospital.id, test_id) is None:
        return JSONResponse({"error": "No such test."}, status_code=404)
    label = ((payload or {}).get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "label is required."}, status_code=400)
    price = (payload or {}).get("price")
    preparation_instructions = ((payload or {}).get("preparation_instructions") or "").strip() or None
    variant = db.create_variant(hospital.id, test_id, label, price, preparation_instructions)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test_variant.create",
        entity_type="diagnostic_test_variant", entity_id=str(variant["id"]), after=variant,
    )
    return JSONResponse({"variant": variant})


@router.put("/api/portal/diagnostic-tests/variants/{variant_id}")
async def portal_update_variant(variant_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    label = ((payload or {}).get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "label is required."}, status_code=400)
    price = (payload or {}).get("price")
    preparation_instructions = ((payload or {}).get("preparation_instructions") or "").strip() or None
    updated = db.update_variant(hospital.id, variant_id, label, price, preparation_instructions)
    if updated is None:
        return JSONResponse({"error": "No such variant."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test_variant.update",
        entity_type="diagnostic_test_variant", entity_id=str(variant_id), after=updated,
    )
    return JSONResponse({"variant": updated})


@router.post("/api/portal/diagnostic-tests/variants/{variant_id}/active")
async def portal_set_variant_active(variant_id: int, payload: dict, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    is_active = bool((payload or {}).get("is_active", True))
    updated = db.set_variant_active(hospital.id, variant_id, is_active)
    if updated is None:
        return JSONResponse({"error": "No such variant."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test_variant.toggle",
        entity_type="diagnostic_test_variant", entity_id=str(variant_id), after={"is_active": is_active},
    )
    return JSONResponse({"variant": updated})


@router.delete("/api/portal/diagnostic-tests/variants/{variant_id}")
async def portal_delete_variant(variant_id: int, authorization: str | None = Header(default=None)):
    hospital = _authenticate(authorization)
    if hospital is None:
        return JSONResponse({"error": "Not authenticated."}, status_code=401)
    forbidden = require_capability(hospital, "manage_appointment_types")
    if forbidden:
        return forbidden
    deleted = db.delete_variant(hospital.id, variant_id)
    if not deleted:
        return JSONResponse({"error": "No such variant."}, status_code=404)
    db.record_audit_log(
        "portal", hospital.id, "tenant portal", "diagnostic_test_variant.delete",
        entity_type="diagnostic_test_variant", entity_id=str(variant_id),
    )
    return JSONResponse({"deleted": True})
