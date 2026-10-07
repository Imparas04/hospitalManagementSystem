"""Wards, beds and patient admission/discharge.

Smart automatic bed allocation (ward type + bed type + gender + emergency
priority + ICU/isolation rules) is built in Phase 4. Here, admission is a
manual bed pick by reception/nursing staff - a necessary foundation step
(you cannot allocate automatically without wards/beds existing first).
"""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required, roles_required
from app.models.bed import BED_STATUSES, Admission, Bed, Ward
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.role import ROLE_ADMIN
from app.services import admission_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_admission_payload, validate_bed_payload, validate_ward_payload

bp = Blueprint("admissions", __name__, url_prefix="/api")


# --------------------------------------------------------------- wards --

@bp.post("/wards")
@roles_required(ROLE_ADMIN)
def create_ward():
    data = request.get_json(silent=True) or {}
    errors = validate_ward_payload(data)
    if not errors and Ward.query.filter_by(name=data["name"].strip()).first():
        errors["name"] = "Ward name already exists"
    if errors:
        return error_response("Validation failed", errors, 400)
    ward = admission_service.create_ward(data)
    return success_response("Ward created successfully", ward.to_dict(), 201)


@bp.get("/wards")
@permission_required("wards:read")
def list_wards():
    wards = Ward.query.filter_by(is_active=True).order_by(Ward.name).all()
    return success_response("Wards fetched", [w.to_dict() for w in wards])


# ---------------------------------------------------------------- beds --

@bp.post("/wards/<int:ward_id>/beds")
@roles_required(ROLE_ADMIN)
def add_bed(ward_id):
    ward = db.session.get(Ward, ward_id)
    if not ward:
        return error_response("Ward not found", status=404)
    data = request.get_json(silent=True) or {}
    errors = validate_bed_payload(data)
    if not errors and Bed.query.filter_by(ward_id=ward.id, bed_number=data["bed_number"].strip()).first():
        errors["bed_number"] = "Bed number already exists in this ward"
    if errors:
        return error_response("Validation failed", errors, 400)
    bed = admission_service.add_bed(ward, data)
    return success_response("Bed added successfully", bed.to_dict(), 201)


@bp.get("/beds")
@permission_required("beds:read")
def list_beds():
    """Query params: ward_id, status (available|occupied|maintenance), bed_type."""
    beds = admission_service.search_beds(request.args).all()
    return success_response("Beds fetched", [b.to_dict() for b in beds])


@bp.put("/beds/<int:bed_id>")
@permission_required("beds:update")
def update_bed(bed_id):
    bed = db.session.get(Bed, bed_id)
    if not bed:
        return error_response("Bed not found", status=404)
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in BED_STATUSES:
        return error_response("Validation failed", {"status": f"status must be one of: {', '.join(BED_STATUSES)}"}, 400)
    if bed.status == "occupied" and status == "available":
        return error_response("Cannot free an occupied bed directly - discharge the patient instead", status=400)
    bed = admission_service.update_bed_status(bed, status)
    return success_response("Bed updated successfully", bed.to_dict())


# ---------------------------------------------------------- admissions --

@bp.post("/admissions")
@permission_required("admissions:create")
def admit_patient():
    data = request.get_json(silent=True) or {}
    errors = validate_admission_payload(data)
    if not errors:
        if not db.session.get(Patient, data["patient_id"]):
            errors["patient_id"] = "Patient not found"
        if not db.session.get(Doctor, data["doctor_id"]):
            errors["doctor_id"] = "Doctor not found"
    if errors:
        return error_response("Validation failed", errors, 400)

    admission, err = admission_service.admit_patient(data, admitted_by_id=g.current_user.id)
    if err:
        return error_response(err, status=409)
    return success_response("Patient admitted successfully", admission.to_dict(), 201)


@bp.get("/admissions")
@permission_required("admissions:read")
def list_admissions():
    """Query params: patient_id, status (admitted|discharged), ward_id, page, per_page."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)
    result = admission_service.search_admissions(request.args).paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Admissions fetched", {
        "items": [a.to_dict() for a in result.items],
        "page": result.page, "per_page": result.per_page,
        "total": result.total, "pages": result.pages,
    })


@bp.get("/admissions/<int:admission_id>")
@permission_required("admissions:read")
def get_admission(admission_id):
    admission = db.session.get(Admission, admission_id)
    if not admission:
        return error_response("Admission not found", status=404)
    return success_response("Admission fetched", admission.to_dict())


@bp.post("/admissions/<int:admission_id>/discharge")
@permission_required("admissions:update")
def discharge_patient(admission_id):
    admission = db.session.get(Admission, admission_id)
    if not admission:
        return error_response("Admission not found", status=404)
    if admission.status == "discharged":
        return error_response("Patient is already discharged", status=400)
    admission = admission_service.discharge_patient(admission)
    return success_response("Patient discharged successfully", admission.to_dict())
