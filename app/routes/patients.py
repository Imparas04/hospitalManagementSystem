"""Patient Management APIs.

Permissions (see app/utils/permissions.py):
  patients:read   -> receptionist, doctor, nurse
  patients:create -> receptionist
  patients:update -> receptionist, doctor
Admin always has access (permission_required treats "*" as all-permissions).
"""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required
from app.models.patient import Patient
from app.services import patient_service
from app.utils.responses import error_response, success_response
from app.utils.validators import (
    validate_medical_history_payload, validate_patient_payload, validate_visit_payload,
)

bp = Blueprint("patients", __name__, url_prefix="/api/patients")


@bp.post("")
@permission_required("patients:create")
def create_patient():
    data = request.get_json(silent=True) or {}
    errors = validate_patient_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)

    patient = patient_service.create_patient(data, created_by_id=g.current_user.id)
    return success_response("Patient registered successfully", patient.to_dict(), 201)


@bp.get("")
@permission_required("patients:read")
def list_patients():
    """Query params: q (name/code/phone), gender, blood_group, emergency=true,
    min_age, max_age, is_active (default true), page, per_page."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)
    for field in ("min_age", "max_age"):
        val = request.args.get(field)
        if val is not None and not val.isdigit():
            return error_response("Validation failed", {field: "must be a whole number"}, 400)

    query = patient_service.search_patients(request.args)
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Patients fetched", {
        "items": [p.to_dict() for p in result.items],
        "page": result.page, "per_page": result.per_page,
        "total": result.total, "pages": result.pages,
    })


def _get_patient_or_404(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return None, error_response("Patient not found", status=404)
    return patient, None


@bp.get("/<int:patient_id>")
@permission_required("patients:read")
def get_patient(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    include_history = request.args.get("include_history") == "true"
    return success_response("Patient fetched", patient.to_dict(include_history=include_history))


@bp.put("/<int:patient_id>")
@permission_required("patients:update")
def update_patient(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Validation failed", {"body": "No data provided"}, 400)
    errors = validate_patient_payload(data, partial=True)
    if errors:
        return error_response("Validation failed", errors, 400)
    patient = patient_service.update_patient(patient, data)
    return success_response("Patient updated successfully", patient.to_dict())


@bp.delete("/<int:patient_id>")
@permission_required("patients:update")
def deactivate_patient(patient_id):
    """Soft delete - patient records are never hard-deleted (medical/legal history)."""
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    patient.is_active = False
    db.session.commit()
    return success_response("Patient deactivated successfully", patient.to_dict())


# ---------------------------------------------------------------- history --

@bp.post("/<int:patient_id>/medical-history")
@permission_required("patients:update")
def add_medical_history(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    errors = validate_medical_history_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    entry = patient_service.add_medical_history(patient, data, recorded_by_id=g.current_user.id)
    return success_response("Medical history entry added", entry.to_dict(), 201)


@bp.get("/<int:patient_id>/medical-history")
@permission_required("patients:read")
def list_medical_history(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    return success_response("Medical history fetched", [h.to_dict() for h in patient.medical_history])


@bp.post("/<int:patient_id>/visits")
@permission_required("patients:update")
def add_visit(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    errors = validate_visit_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    visit = patient_service.add_visit(patient, data, recorded_by_id=g.current_user.id)
    return success_response("Visit recorded", visit.to_dict(), 201)


@bp.get("/<int:patient_id>/visits")
@permission_required("patients:read")
def list_visits(patient_id):
    patient, err = _get_patient_or_404(patient_id)
    if err:
        return err
    return success_response("Visit history fetched", [v.to_dict() for v in patient.visits])
