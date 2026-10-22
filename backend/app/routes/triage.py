"""Emergency & Triage module: record vitals, compute priority, maintain the
emergency queue, and trigger automatic smart bed allocation."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required
from app.models.patient import Patient
from app.models.triage import STATUS_RESOLVED, STATUS_WAITING, TriageRecord
from app.services import triage_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_triage_payload, validate_triage_status_payload

bp = Blueprint("triage", __name__, url_prefix="/api/triage")


@bp.post("")
@permission_required("triage:create")
def create_triage():
    """Record vital signs for a patient. Priority level/score are calculated
    automatically (see app/services/triage_service.py::calculate_priority)."""
    data = request.get_json(silent=True) or {}
    errors = validate_triage_payload(data)
    if not errors and not db.session.get(Patient, data["patient_id"]):
        errors["patient_id"] = "Patient not found"
    if errors:
        return error_response("Validation failed", errors, 400)

    record = triage_service.create_triage_record(data, recorded_by_id=g.current_user.id)
    return success_response("Triage recorded successfully", record.to_dict(), 201)


@bp.get("/queue")
@permission_required("triage:read")
def get_queue():
    """The emergency queue: waiting patients sorted most-urgent-first."""
    records = triage_service.emergency_queue()
    return success_response("Emergency queue fetched", [r.to_dict() for r in records])


@bp.get("")
@permission_required("triage:read")
def list_triage():
    """Query params: status, priority_level, patient_id."""
    q = TriageRecord.query
    for field, column in (("status", TriageRecord.status), ("priority_level", TriageRecord.priority_level),
                          ("patient_id", TriageRecord.patient_id)):
        val = request.args.get(field)
        if val:
            q = q.filter(column == val)
    records = q.order_by(TriageRecord.recorded_at.desc()).all()
    return success_response("Triage records fetched", [r.to_dict() for r in records])


def _get_or_404(triage_id):
    record = db.session.get(TriageRecord, triage_id)
    if not record:
        return None, error_response("Triage record not found", status=404)
    return record, None


@bp.get("/<int:triage_id>")
@permission_required("triage:read")
def get_triage(triage_id):
    record, err = _get_or_404(triage_id)
    if err:
        return err
    return success_response("Triage record fetched", record.to_dict())


@bp.put("/<int:triage_id>/status")
@permission_required("triage:update")
def update_status(triage_id):
    """Move a patient through the emergency workflow: waiting -> bed_assigned
    -> in_treatment -> resolved. (bed_assigned is normally set automatically
    by POST /<id>/allocate-bed, not set here.)"""
    record, err = _get_or_404(triage_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    errors = validate_triage_status_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    record.status = data["status"]
    db.session.commit()
    return success_response("Triage status updated", record.to_dict())


@bp.post("/<int:triage_id>/allocate-bed")
@permission_required("triage:update")
def allocate_bed(triage_id):
    """Automatic smart bed allocation for this triage record.

    Looks at icu_required / isolation_required / patient gender, finds the
    best matching available bed, admits the patient into it, and links the
    admission back onto this triage record. Needs doctor_id in the body
    (who is treating this patient)."""
    record, err = _get_or_404(triage_id)
    if err:
        return err
    if record.status != STATUS_WAITING:
        return error_response(f"Cannot allocate a bed - triage status is already '{record.status}'", status=400)

    data = request.get_json(silent=True) or {}
    doctor_id = data.get("doctor_id")
    if not isinstance(doctor_id, int):
        return error_response("Validation failed", {"doctor_id": "doctor_id is required"}, 400)

    admission, err_msg = triage_service.allocate_bed_for_triage(record, doctor_id, admitted_by_id=g.current_user.id)
    if err_msg:
        return error_response(err_msg, status=409)
    return success_response("Bed allocated and patient admitted automatically", {
        "triage": record.to_dict(), "admission": admission.to_dict(),
    }, 201)


@bp.post("/<int:triage_id>/resolve")
@permission_required("triage:update")
def resolve_triage(triage_id):
    record, err = _get_or_404(triage_id)
    if err:
        return err
    record.status = STATUS_RESOLVED
    db.session.commit()
    return success_response("Triage case resolved", record.to_dict())
