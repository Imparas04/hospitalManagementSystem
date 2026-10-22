"""Pharmacy module: medicine catalog + stock batches, and prescriptions
(doctor prescribes, pharmacist issues with FEFO logic, expired stock blocked,
low-stock visible via GET /medicines?low_stock=true)."""
from flask import Blueprint, g, request

from app.extensions import db
from app.middleware.auth import permission_required, roles_required
from app.models.patient import Patient
from app.models.pharmacy import Medicine, MedicineBatch, Prescription
from app.models.role import ROLE_ADMIN, ROLE_PHARMACIST
from app.services import pharmacy_service
from app.utils.responses import error_response, success_response
from app.utils.validators import validate_batch_payload, validate_medicine_payload, validate_prescription_payload

bp = Blueprint("pharmacy", __name__, url_prefix="/api")


def _current_doctor_or_none():
    from app.models.doctor import Doctor
    return Doctor.query.filter_by(user_id=g.current_user.id).first()


# --------------------------------------------------------------- medicines --

@bp.post("/pharmacy/medicines")
@roles_required(ROLE_ADMIN, ROLE_PHARMACIST)
def create_medicine():
    data = request.get_json(silent=True) or {}
    errors = validate_medicine_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    if Medicine.query.filter_by(name=data["name"].strip()).first():
        return error_response("Medicine already exists", {"name": "A medicine with this name already exists"}, 409)
    medicine = pharmacy_service.create_medicine(data)
    return success_response("Medicine created successfully", medicine.to_dict(), 201)


@bp.get("/pharmacy/medicines")
@permission_required("pharmacy:read")
def list_medicines():
    """Query params: q (search name), low_stock=true."""
    medicines = pharmacy_service.search_medicines(request.args)
    return success_response("Medicines fetched", [m.to_dict() for m in medicines])


@bp.get("/pharmacy/medicines/<int:medicine_id>")
@permission_required("pharmacy:read")
def get_medicine(medicine_id):
    medicine = db.session.get(Medicine, medicine_id)
    if not medicine:
        return error_response("Medicine not found", status=404)
    data = medicine.to_dict()
    data["batches"] = [b.to_dict() for b in medicine.batches]
    return success_response("Medicine fetched", data)


@bp.post("/pharmacy/medicines/<int:medicine_id>/batches")
@permission_required("pharmacy:update")
def add_batch(medicine_id):
    medicine = db.session.get(Medicine, medicine_id)
    if not medicine:
        return error_response("Medicine not found", status=404)
    data = request.get_json(silent=True) or {}
    errors = validate_batch_payload(data)
    if not errors and MedicineBatch.query.filter_by(
        medicine_id=medicine.id, batch_number=data["batch_number"].strip()
    ).first():
        errors["batch_number"] = "This batch number already exists for this medicine"
    if errors:
        return error_response("Validation failed", errors, 400)

    import datetime as _dt
    data = {**data, "expiry_date": _dt.datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()}
    batch = pharmacy_service.add_batch(medicine, data)
    return success_response("Stock batch added successfully", batch.to_dict(), 201)


# ------------------------------------------------------------ prescriptions --

@bp.post("/prescriptions")
@permission_required("prescriptions:create")
def create_prescription():
    data = request.get_json(silent=True) or {}
    errors = validate_prescription_payload(data)
    if not errors:
        if not db.session.get(Patient, data["patient_id"]):
            errors["patient_id"] = "Patient not found"
        for i, item in enumerate(data.get("items", [])):
            if isinstance(item.get("medicine_id"), int) and not db.session.get(Medicine, item["medicine_id"]):
                errors.setdefault("items", [{} for _ in data["items"]])
                errors["items"][i]["medicine_id"] = "Medicine not found"
    if errors:
        return error_response("Validation failed", errors, 400)

    doctor = _current_doctor_or_none()
    if doctor is None:
        return error_response("Your account has no linked doctor profile", status=400)
    prescription = pharmacy_service.create_prescription(data, doctor_id=doctor.id)
    return success_response("Prescription created successfully", prescription.to_dict(), 201)


@bp.get("/prescriptions")
@permission_required("prescriptions:read")
def list_prescriptions():
    """Query params: patient_id, doctor_id, status."""
    q = Prescription.query
    for field, column in (("patient_id", Prescription.patient_id), ("doctor_id", Prescription.doctor_id)):
        val = request.args.get(field)
        if val:
            q = q.filter(column == int(val))
    status = request.args.get("status")
    if status:
        q = q.filter(Prescription.status == status)
    prescriptions = q.order_by(Prescription.created_at.desc()).all()
    return success_response("Prescriptions fetched", [p.to_dict() for p in prescriptions])


@bp.get("/prescriptions/<int:prescription_id>")
@permission_required("prescriptions:read")
def get_prescription(prescription_id):
    prescription = db.session.get(Prescription, prescription_id)
    if not prescription:
        return error_response("Prescription not found", status=404)
    return success_response("Prescription fetched", prescription.to_dict())


@bp.post("/prescriptions/<int:prescription_id>/issue")
@permission_required("pharmacy:issue")
def issue_prescription(prescription_id):
    """Issues as much of the prescription as stock allows (FEFO, skips expired
    batches). Returns a per-medicine breakdown of what was issued vs short."""
    prescription = db.session.get(Prescription, prescription_id)
    if not prescription:
        return error_response("Prescription not found", status=404)
    if prescription.status == "issued":
        return error_response("Prescription has already been fully issued", status=400)

    breakdown = pharmacy_service.issue_prescription(prescription)
    return success_response("Prescription processed", {
        "prescription": prescription.to_dict(), "breakdown": breakdown,
    })
