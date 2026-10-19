"""Laboratory module: test catalog, doctor orders a test, lab tech processes
it and enters the result, doctor reviews it."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required, roles_required
from app.models.lab import LabOrder, LabTest
from app.models.patient import Patient
from app.models.role import ROLE_ADMIN, ROLE_LAB_TECH
from app.services import lab_service
from app.utils.responses import error_response, success_response
from app.utils.validators import (
    validate_lab_order_payload, validate_lab_result_payload, validate_lab_status_payload, validate_lab_test_payload,
)

bp = Blueprint("lab", __name__, url_prefix="/api/lab")


# ----------------------------------------------------------------- catalog --

@bp.post("/tests")
@roles_required(ROLE_ADMIN, ROLE_LAB_TECH)
def create_test_type():
    data = request.get_json(silent=True) or {}
    errors = validate_lab_test_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    if LabTest.query.filter_by(code=data["code"].strip().upper()).first():
        return error_response("Lab test already exists", {"code": "A test with this code already exists"}, 409)
    test = lab_service.create_test_type(data)
    return success_response("Lab test type created successfully", test.to_dict(), 201)


@bp.get("/tests")
@permission_required("lab:read")
def list_test_types():
    tests = LabTest.query.filter_by(is_active=True).order_by(LabTest.name).all()
    return success_response("Lab test types fetched", [t.to_dict() for t in tests])


# ------------------------------------------------------------------ orders --

@bp.post("/orders")
@permission_required("lab:order")
def create_order():
    data = request.get_json(silent=True) or {}
    errors = validate_lab_order_payload(data)
    if not errors:
        if not db.session.get(Patient, data["patient_id"]):
            errors["patient_id"] = "Patient not found"
        if not db.session.get(LabTest, data["lab_test_id"]):
            errors["lab_test_id"] = "Lab test type not found"
    if errors:
        return error_response("Validation failed", errors, 400)

    doctor = _current_doctor_or_none()
    if doctor is None:
        return error_response("Your account has no linked doctor profile", status=400)
    order = lab_service.create_order(data, doctor_id=doctor.id)
    return success_response("Lab test ordered successfully", order.to_dict(), 201)


def _current_doctor_or_none():
    from app.models.doctor import Doctor
    return Doctor.query.filter_by(user_id=g.current_user.id).first()


@bp.get("/orders")
@permission_required("lab:read")
def list_orders():
    """Query params: patient_id, doctor_id, status."""
    orders = lab_service.search_orders(request.args).all()
    return success_response("Lab orders fetched", [o.to_dict() for o in orders])


def _get_or_404(order_id):
    order = db.session.get(LabOrder, order_id)
    if not order:
        return None, error_response("Lab order not found", status=404)
    return order, None


@bp.get("/orders/<int:order_id>")
@permission_required("lab:read")
def get_order(order_id):
    order, err = _get_or_404(order_id)
    if err:
        return err
    return success_response("Lab order fetched", order.to_dict())


@bp.put("/orders/<int:order_id>/status")
@permission_required("lab:update")
def update_order_status(order_id):
    """Lab tech moves the order through: sample_collected -> processing."""
    order, err = _get_or_404(order_id)
    if err:
        return err
    if order.status in ("result_entered", "reviewed"):
        return error_response(f"Cannot change status - result already entered ({order.status})", status=400)
    data = request.get_json(silent=True) or {}
    errors = validate_lab_status_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    order = lab_service.advance_status(order, data["status"])
    return success_response("Lab order status updated", order.to_dict())


@bp.post("/orders/<int:order_id>/result")
@permission_required("lab:enter_result")
def enter_result(order_id):
    order, err = _get_or_404(order_id)
    if err:
        return err
    if order.status == "reviewed":
        return error_response("Result has already been reviewed", status=400)
    if order.result is not None:
        return error_response("Result has already been entered for this order", status=400)
    data = request.get_json(silent=True) or {}
    errors = validate_lab_result_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    lab_service.enter_result(order, data, entered_by_id=g.current_user.id)
    return success_response("Result entered successfully", order.to_dict(), 201)


@bp.post("/orders/<int:order_id>/review")
@permission_required("lab:review")
def review_order(order_id):
    """Doctor reviews the entered result."""
    order, err = _get_or_404(order_id)
    if err:
        return err
    if order.result is None:
        return error_response("No result has been entered yet", status=400)
    if order.status == "reviewed":
        return error_response("Result has already been reviewed", status=400)
    data = request.get_json(silent=True) or {}
    order = lab_service.review_result(order, data.get("reviewer_notes"), reviewed_by_id=g.current_user.id)
    return success_response("Result reviewed successfully", order.to_dict())
