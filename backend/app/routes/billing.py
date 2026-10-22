"""Billing: automatic bill generation, discounts/tax, payments, receipts, PDFs.

Roles: billing_staff (and admin). PDF endpoints return application/pdf. Because
the JWT travels in a header, a plain <a href> cannot open them - the frontend must
fetch() with the Authorization header and show the blob (see docs/API_Phase_06.md).
"""
from flask import Blueprint, Response, g, request

from app.extensions import db
from app.middleware.auth import permission_required
from app.models.billing import BILL_PAID, Bill, Payment
from app.models.patient import Patient
from app.services import billing_service, pdf_service
from app.utils.responses import error_response, success_response
from app.utils.validators import (
    validate_adjust_payload, validate_bill_payload, validate_other_service, validate_payment_payload,
)

bp = Blueprint("billing", __name__, url_prefix="/api")


def pdf_response(data, filename):
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


def _find_patient(data):
    """Billing staff identify a patient by patient_id OR by the printed patient_code."""
    if data.get("patient_id") is not None:
        return db.session.get(Patient, data["patient_id"])
    return Patient.query.filter_by(patient_code=data.get("patient_code")).first()


def _bill_or_404(bill_id):
    bill = db.session.get(Bill, bill_id)
    if not bill:
        return None, error_response("Bill not found", status=404)
    return bill, None


# ------------------------------------------------------------------- bills --

@bp.get("/bills/preview")
@permission_required("billing:read")
def preview_bill():
    """Shows what WOULD be billed right now (nothing is saved). Query: patient_id or patient_code."""
    patient = _find_patient({"patient_id": request.args.get("patient_id", type=int),
                             "patient_code": request.args.get("patient_code")})
    if not patient:
        return error_response("Patient not found", status=404)
    lines = billing_service.collect_billable_items(patient)
    subtotal = sum((l["amount"] for l in lines), billing_service.money(0))
    return success_response("Billable items fetched", {
        "patient_id": patient.id, "patient_code": patient.patient_code, "patient_name": patient.full_name,
        "items": [{k: (float(v) if k in ("unit_price", "amount") else v) for k, v in l.items()
                   if k in ("category", "description", "quantity", "unit_price", "amount")} for l in lines],
        "subtotal": float(subtotal),
    })


@bp.post("/bills")
@permission_required("billing:create")
def create_bill():
    """Automatic billing: collects every unbilled service for the patient into one bill."""
    data = request.get_json(silent=True) or {}
    errors = validate_bill_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    patient = _find_patient(data)
    if not patient:
        return error_response("Patient not found", status=404)

    bill = billing_service.generate_bill(
        patient, created_by_id=g.current_user.id, discount_percent=data.get("discount_percent", 0),
        tax_percent=data.get("tax_percent"), other_services=data.get("other_services"))
    if bill is None:
        return error_response("Nothing to bill - this patient has no unbilled services", status=409)
    return success_response("Bill generated successfully", bill.to_dict(include_details=True), 201)


@bp.get("/bills")
@permission_required("billing:read")
def list_bills():
    """Query: patient_id, patient_code, status (unpaid|partially_paid|paid), page, per_page."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page < 1 or per_page < 1:
        return error_response("page and per_page must be positive numbers", status=400)
    result = billing_service.search_bills(request.args).paginate(page=page, per_page=per_page, error_out=False)
    return success_response("Bills fetched", {
        "items": [b.to_dict() for b in result.items], "page": result.page, "per_page": result.per_page,
        "total": result.total, "pages": result.pages})


@bp.get("/bills/outstanding")
@permission_required("billing:read")
def outstanding_bills():
    """Every bill that still has money due, oldest first, plus the grand total due."""
    bills = Bill.query.filter(Bill.status != BILL_PAID).order_by(Bill.id).all()
    total = sum((b.outstanding for b in bills), billing_service.money(0))
    return success_response("Outstanding bills fetched", {
        "total_outstanding": float(total), "count": len(bills), "bills": [b.to_dict() for b in bills]})


@bp.get("/bills/<int:bill_id>")
@permission_required("billing:read")
def get_bill(bill_id):
    bill, err = _bill_or_404(bill_id)
    if err:
        return err
    return success_response("Bill fetched", bill.to_dict(include_details=True))


@bp.post("/bills/<int:bill_id>/items")
@permission_required("billing:update")
def add_item(bill_id):
    """Add an 'other service' line (e.g. ambulance, dressing). Not allowed on a fully paid bill."""
    bill, err = _bill_or_404(bill_id)
    if err:
        return err
    if bill.status == BILL_PAID:
        return error_response("Cannot add items to a fully paid bill", status=400)
    data = request.get_json(silent=True) or {}
    errors = validate_other_service(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    bill = billing_service.add_other_service(bill, data)
    return success_response("Item added to bill", bill.to_dict(include_details=True), 201)


@bp.put("/bills/<int:bill_id>/adjust")
@permission_required("billing:update")
def adjust_bill(bill_id):
    """Change discount % and/or tax %. Only before any payment has been taken."""
    bill, err = _bill_or_404(bill_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    errors = validate_adjust_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    if bill.amount_paid > 0:
        return error_response("Discount/tax cannot be changed after a payment has been received", status=400)
    bill = billing_service.adjust_bill(bill, data.get("discount_percent"), data.get("tax_percent"))
    return success_response("Bill adjusted", bill.to_dict(include_details=True))


@bp.get("/bills/<int:bill_id>/pdf")
@permission_required("billing:read")
def bill_pdf(bill_id):
    bill, err = _bill_or_404(bill_id)
    if err:
        return err
    return pdf_response(pdf_service.invoice_pdf(bill), f"{bill.bill_number}.pdf")


# ---------------------------------------------------------------- payments --

@bp.post("/bills/<int:bill_id>/payments")
@permission_required("payments:create")
def add_payment(bill_id):
    """Take a payment (partial or full, any method). Returns the receipt data."""
    bill, err = _bill_or_404(bill_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    errors = validate_payment_payload(data)
    if errors:
        return error_response("Validation failed", errors, 400)
    payment, msg = billing_service.record_payment(
        bill, data["amount"], data["method"], data.get("reference"), received_by_id=g.current_user.id)
    if msg:
        return error_response(msg, status=400)
    return success_response("Payment recorded", {
        "payment": payment.to_dict(), "bill": payment.bill.to_dict()}, 201)


def _payment_or_404(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        return None, error_response("Payment not found", status=404)
    return payment, None


@bp.get("/payments/<int:payment_id>/receipt")
@permission_required("billing:read")
def receipt_json(payment_id):
    payment, err = _payment_or_404(payment_id)
    if err:
        return err
    bill = payment.bill
    return success_response("Receipt fetched", {
        "payment": payment.to_dict(), "bill_number": bill.bill_number, "patient_name": bill.patient.full_name,
        "patient_code": bill.patient.patient_code, "bill_total": float(bill.total_amount),
        "balance_after_payment": float(billing_service.balance_after(payment))})


@bp.get("/payments/<int:payment_id>/receipt/pdf")
@permission_required("billing:read")
def receipt_pdf(payment_id):
    payment, err = _payment_or_404(payment_id)
    if err:
        return err
    return pdf_response(pdf_service.receipt_pdf(payment), f"{payment.receipt_number}.pdf")
