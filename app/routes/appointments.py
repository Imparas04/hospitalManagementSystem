"""Appointment booking, listing, rescheduling, cancellation and waiting list."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required
from app.models.appointment import (
    STATUS_CANCELLED, STATUS_COMPLETED, STATUS_NO_SHOW, STATUS_WAITLISTED, Appointment,
)
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.services import appointment_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_appointment_payload

bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")


def _check_refs(data):
    """Shared FK checks used by create and reschedule."""
    errors = {}
    if "patient_id" in data and not db.session.get(Patient, data["patient_id"]):
        errors["patient_id"] = "Patient not found"
    if "doctor_id" in data and not db.session.get(Doctor, data["doctor_id"]):
        errors["doctor_id"] = "Doctor not found"
    return errors


@bp.post("")
@permission_required("appointments:create")
def book_appointment():
    """Books the requested slot if free. If taken, the appointment is created as
    'waitlisted' instead of failing (unless allow_waitlist: false is sent,
    in which case a 409 is returned so the frontend can show 'slot taken')."""
    data = request.get_json(silent=True) or {}
    errors = validate_appointment_payload(data)
    errors.update(_check_refs(data))
    if errors:
        return error_response("Validation failed", errors, 400)

    appointment, was_waitlisted = appointment_service.book_appointment(data, created_by_id=g.current_user.id)
    if appointment is None:
        return error_response("Requested slot is not available", status=409)

    message = "Doctor is fully booked for this slot - added to the waiting list" if was_waitlisted \
        else "Appointment booked successfully"
    return success_response(message, appointment.to_dict(), 201)


@bp.get("")
@permission_required("appointments:read")
def list_appointments():
    """Query params: doctor_id, patient_id, department_id, status, date (YYYY-MM-DD), page, per_page."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)

    query = appointment_service.search_appointments(request.args)
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Appointments fetched", {
        "items": [a.to_dict() for a in result.items],
        "page": result.page, "per_page": result.per_page,
        "total": result.total, "pages": result.pages,
    })


@bp.get("/waiting-list")
@permission_required("appointments:read")
def waiting_list():
    """Query params: doctor_id, department_id (optional filters)."""
    params = dict(request.args)
    params["status"] = STATUS_WAITLISTED
    appts = appointment_service.search_appointments(params).all()
    return success_response("Waiting list fetched", [a.to_dict() for a in appts])


def _get_or_404(appointment_id):
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return None, error_response("Appointment not found", status=404)
    return appt, None


@bp.get("/<int:appointment_id>")
@permission_required("appointments:read")
def get_appointment(appointment_id):
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    return success_response("Appointment fetched", appt.to_dict())


@bp.put("/<int:appointment_id>")
@permission_required("appointments:update")
def reschedule_appointment(appointment_id):
    """Reschedule: send any of appointment_date, appointment_time, doctor_id, reason, notes."""
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    if appt.status in (STATUS_CANCELLED, STATUS_COMPLETED):
        return error_response(f"Cannot modify a {appt.status} appointment", status=400)

    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Validation failed", {"body": "No data provided"}, 400)
    errors = validate_appointment_payload(data, partial=True)
    errors.update(_check_refs(data))
    if errors:
        return error_response("Validation failed", errors, 400)

    if "reason" in data:
        appt.reason = data["reason"].strip()
    if "notes" in data:
        appt.notes = data["notes"] or None

    if "appointment_date" in data or "appointment_time" in data or "doctor_id" in data:
        updated = appointment_service.reschedule_appointment(appt, data)
        if updated is None:
            return error_response("Requested slot is not available", status=409)
        appt = updated
    else:
        db.session.commit()
    return success_response("Appointment updated successfully", appt.to_dict())


@bp.post("/<int:appointment_id>/cancel")
@permission_required("appointments:update")
def cancel_appointment(appointment_id):
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    if appt.status in (STATUS_CANCELLED, STATUS_COMPLETED):
        return error_response(f"Appointment is already {appt.status}", status=400)
    appointment_service.set_status(appt, STATUS_CANCELLED)
    return success_response("Appointment cancelled successfully", appt.to_dict())


@bp.post("/<int:appointment_id>/complete")
@permission_required("appointments:update")
def complete_appointment(appointment_id):
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    if appt.status != "scheduled":
        return error_response("Only a scheduled appointment can be marked completed", status=400)
    appointment_service.set_status(appt, STATUS_COMPLETED)
    return success_response("Appointment marked completed", appt.to_dict())


@bp.post("/<int:appointment_id>/no-show")
@permission_required("appointments:update")
def no_show_appointment(appointment_id):
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    if appt.status != "scheduled":
        return error_response("Only a scheduled appointment can be marked no-show", status=400)
    appointment_service.set_status(appt, STATUS_NO_SHOW)
    return success_response("Appointment marked as no-show", appt.to_dict())


@bp.post("/<int:appointment_id>/promote")
@permission_required("appointments:update")
def promote_waitlisted(appointment_id):
    """Try to move a waitlisted appointment into its requested slot (e.g. after a cancellation freed it up)."""
    appt, err = _get_or_404(appointment_id)
    if err:
        return err
    if appt.status != STATUS_WAITLISTED:
        return error_response("Only a waitlisted appointment can be promoted", status=400)
    if not appointment_service.promote_from_waitlist(appt):
        return error_response("Slot is still not available", status=409)
    return success_response("Appointment promoted from waiting list", appt.to_dict())
