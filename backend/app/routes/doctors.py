"""Department and Doctor management.

Create/update department or doctor profile -> ADMIN ONLY (staff structure).
Reading doctors/departments and schedules -> anyone with doctors:read / departments:read
(receptionist, doctor, nurse, admin) - needed for booking appointments.
"""
from datetime import datetime

from flask import Blueprint, request

from app.extensions import db
from app.middleware.auth import permission_required, roles_required
from app.models.doctor import Department, Doctor
from app.models.role import ROLE_ADMIN, ROLE_DOCTOR
from app.models.user import User
from app.services import doctor_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_department_payload, validate_doctor_payload, validate_schedule_payload

bp = Blueprint("doctors", __name__, url_prefix="/api")


# ------------------------------------------------------------ departments --

@bp.post("/departments")
@roles_required(ROLE_ADMIN)
def create_department():
    data = request.get_json(silent=True) or {}
    errors = validate_department_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    if Department.query.filter_by(name=data["name"].strip()).first():
        return error_response("Department already exists", {"name": "Department name already exists"}, 409)
    dept = doctor_service.create_department(data)
    return success_response("Department created successfully", dept.to_dict(), 201)


@bp.get("/departments")
@permission_required("departments:read")
def list_departments():
    q = Department.query
    if request.args.get("is_active", "true") in ("true", "false"):
        q = q.filter(Department.is_active == (request.args.get("is_active", "true") == "true"))
    return success_response("Departments fetched", [d.to_dict() for d in q.order_by(Department.name).all()])


@bp.put("/departments/<int:dept_id>")
@roles_required(ROLE_ADMIN)
def update_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        return error_response("Department not found", status=404)
    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Validation failed", {"body": "No data provided"}, 400)
    errors = validate_department_payload(data, partial=True)
    if errors:
        return error_response("Validation failed", errors, 400)
    dept = doctor_service.update_department(dept, data)
    return success_response("Department updated successfully", dept.to_dict())


# ----------------------------------------------------------------- doctors --

@bp.post("/doctors")
@roles_required(ROLE_ADMIN)
def create_doctor():
    """Links an existing user (role must be 'doctor') to a department + specialization."""
    data = request.get_json(silent=True) or {}
    errors = validate_doctor_payload(data)
    if not errors:
        user = db.session.get(User, data["user_id"])
        if not user:
            errors["user_id"] = "User not found"
        elif user.role.name != ROLE_DOCTOR:
            errors["user_id"] = "That user's account role is not 'doctor'"
        elif Doctor.query.filter_by(user_id=user.id).first():
            errors["user_id"] = "This user already has a doctor profile"
        if not db.session.get(Department, data.get("department_id")):
            errors["department_id"] = "Department not found"
    if errors:
        return error_response("Validation failed", errors, 400)

    doctor = doctor_service.create_doctor(data)
    return success_response("Doctor profile created successfully", doctor.to_dict(), 201)


@bp.get("/doctors")
@permission_required("doctors:read")
def list_doctors():
    """Query params: department_id, specialization, emergency_duty=true, q (name), is_active."""
    doctors = doctor_service.search_doctors(request.args).all()
    return success_response("Doctors fetched", [d.to_dict() for d in doctors])


@bp.get("/doctors/<int:doctor_id>")
@permission_required("doctors:read")
def get_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return error_response("Doctor not found", status=404)
    data = doctor.to_dict()
    data["schedules"] = [s.to_dict() for s in doctor.schedules]
    return success_response("Doctor fetched", data)


@bp.put("/doctors/<int:doctor_id>")
@roles_required(ROLE_ADMIN)
def update_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return error_response("Doctor not found", status=404)
    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Validation failed", {"body": "No data provided"}, 400)
    errors = validate_doctor_payload(data, partial=True)
    if "department_id" in data and not errors.get("department_id") and not db.session.get(Department, data["department_id"]):
        errors["department_id"] = "Department not found"
    if errors:
        return error_response("Validation failed", errors, 400)
    doctor = doctor_service.update_doctor(doctor, data)
    return success_response("Doctor updated successfully", doctor.to_dict())


# -------------------------------------------------------------- schedules --

@bp.post("/doctors/<int:doctor_id>/schedule")
@roles_required(ROLE_ADMIN)
def add_schedule(doctor_id):
    """Add one weekly availability block, e.g. Mon 09:00-13:00 in 15-min slots."""
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return error_response("Doctor not found", status=404)
    data = request.get_json(silent=True) or {}
    errors = validate_schedule_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    schedule = doctor_service.add_schedule(doctor, data)
    return success_response("Schedule added successfully", schedule.to_dict(), 201)


@bp.get("/doctors/<int:doctor_id>/schedule")
@permission_required("doctors:read")
def list_schedule(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return error_response("Doctor not found", status=404)
    return success_response("Schedule fetched", [s.to_dict() for s in doctor.schedules])


@bp.get("/doctors/<int:doctor_id>/availability")
@permission_required("appointments:read")
def doctor_availability(doctor_id):
    """?date=YYYY-MM-DD -> list of free 'HH:MM' slots for that day."""
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return error_response("Doctor not found", status=404)
    date_str = request.args.get("date")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return error_response("Validation failed", {"date": "date is required, format YYYY-MM-DD"}, 400)
    slots = doctor_service.available_slots(doctor.id, target_date)
    return success_response("Available slots fetched", {"date": date_str, "doctor_id": doctor.id, "slots": slots})
