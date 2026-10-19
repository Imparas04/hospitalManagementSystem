"""Automatic billing + payments.

Python Advanced Logic  (Services -> Charges calculation -> Discount -> Tax -> Final amount)

  Consultation charges   completed appointments                    x doctor's consultation_fee
+ Bed / room charges     discharged admissions: days stayed        x ward's daily_charge
+ Laboratory charges     lab orders with a result entered          x test price
+ Medicine charges       quantity actually ISSUED by the pharmacy  x medicine unit price
+ Other services         anything the billing staff types in
----------------------
  Subtotal
- Discount  (subtotal x discount %)
+ Tax       ((subtotal - discount) x tax %)
----------------------
  Final bill

Rules that make it safe:
  * Money uses Decimal (never float) and is rounded to 2 places.
  * Nothing is billed twice: every line remembers its source (e.g. "appointment:5"),
    and a UNIQUE key in the database blocks a duplicate even if two people click at once.
  * Medicines can be billed in several rounds (pharmacy issues part now, rest later):
    each round bills only the quantity not billed yet.
  * Bed charges are billed only after discharge, when the real number of days is known.
"""
import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.appointment import STATUS_COMPLETED, Appointment
from app.models.bed import Admission
from app.models.billing import BILL_PAID, BILL_PARTIAL, BILL_UNPAID, Bill, BillItem, Payment
from app.models.lab import LabOrder
from app.models.pharmacy import Prescription, PrescriptionItem

CENT = Decimal("0.01")


def money(value):
    """Any number -> Decimal rounded to 2 places (half-up, like a calculator)."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def next_number(model, column, letter):
    """B2026000001 / R2026000001 style numbers. The last row is locked while we read it,
    so two simultaneous requests cannot receive the same number."""
    prefix = f"{letter}{date.today().year}"
    last = (model.query.filter(column.like(f"{prefix}%")).order_by(model.id.desc()).with_for_update().first())
    seq = int(getattr(last, column.key)[len(prefix):]) + 1 if last else 1
    return f"{prefix}{seq:06d}"


# ----------------------------------------------------------------------------
# Step 1: find everything that has not been billed yet
# ----------------------------------------------------------------------------

def _billed_keys(keys):
    if not keys:
        return set()
    rows = db.session.query(BillItem.source_key).filter(BillItem.source_key.in_(keys)).all()
    return {r[0] for r in rows}


def _line(category, description, quantity, unit_price, source_type, source_id, one_time=True):
    return {
        "category": category, "description": description, "quantity": quantity,
        "unit_price": money(unit_price), "amount": money(unit_price) * quantity,
        "source_type": source_type, "source_id": source_id,
        "source_key": f"{source_type}:{source_id}" if one_time else None,
    }


def collect_billable_items(patient):
    """Returns a list of line dicts for everything of this patient that is not billed yet."""
    lines = []

    # 1. Consultation - completed appointments
    appts = Appointment.query.filter_by(patient_id=patient.id, status=STATUS_COMPLETED).all()
    done = _billed_keys([f"appointment:{a.id}" for a in appts])
    for a in appts:
        if f"appointment:{a.id}" not in done:
            lines.append(_line("consultation",
                               f"Consultation - Dr. {a.doctor.user.full_name} ({a.appointment_date.isoformat()})",
                               1, a.doctor.consultation_fee, "appointment", a.id))

    # 2. Bed / room - only discharged admissions (so the day count is final)
    admissions = Admission.query.filter_by(patient_id=patient.id, status="discharged").all()
    done = _billed_keys([f"admission:{a.id}" for a in admissions])
    for a in admissions:
        if f"admission:{a.id}" in done:
            continue
        days = max(1, math.ceil((a.discharge_date - a.admission_date).total_seconds() / 86400))
        ward = a.bed.ward
        lines.append(_line("bed", f"Bed charges - {ward.name}, bed {a.bed.bed_number} ({days} day(s))",
                           days, ward.daily_charge, "admission", a.id))

    # 3. Laboratory - results entered or reviewed
    orders = LabOrder.query.filter(LabOrder.patient_id == patient.id,
                                   LabOrder.status.in_(["result_entered", "reviewed"])).all()
    done = _billed_keys([f"lab_order:{o.id}" for o in orders])
    for o in orders:
        if f"lab_order:{o.id}" not in done:
            lines.append(_line("laboratory", f"Lab test - {o.lab_test.name} ({o.lab_test.code})",
                               1, o.lab_test.price, "lab_order", o.id))

    # 4. Medicines - only what the pharmacy has actually issued, minus what was billed before
    items = (PrescriptionItem.query.join(Prescription)
             .filter(Prescription.patient_id == patient.id, PrescriptionItem.quantity_issued > 0).all())
    for item in items:
        already = (db.session.query(db.func.coalesce(db.func.sum(BillItem.quantity), 0))
                   .filter(BillItem.source_type == "prescription_item", BillItem.source_id == item.id).scalar())
        remaining = item.quantity_issued - int(already)
        if remaining > 0:
            lines.append(_line("medicine", f"Medicine - {item.medicine.name} ({item.medicine.unit})",
                               remaining, item.medicine.unit_price, "prescription_item", item.id, one_time=False))
    return lines


# ----------------------------------------------------------------------------
# Step 2/3/4: subtotal -> discount -> tax -> final amount
# ----------------------------------------------------------------------------

def refresh_status(bill):
    paid, total = Decimal(bill.amount_paid or 0), Decimal(bill.total_amount or 0)
    if paid >= total:
        bill.status = BILL_PAID
    elif paid > 0:
        bill.status = BILL_PARTIAL
    else:
        bill.status = BILL_UNPAID


def recalculate(bill):
    subtotal = sum((Decimal(i.amount) for i in bill.items), Decimal("0"))
    subtotal = money(subtotal)
    discount = money(subtotal * Decimal(bill.discount_percent) / 100)
    taxable = subtotal - discount
    tax = money(taxable * Decimal(bill.tax_percent) / 100)
    bill.subtotal, bill.discount_amount, bill.tax_amount = subtotal, discount, tax
    bill.total_amount = taxable + tax
    refresh_status(bill)


def _add_item(bill, line):
    bill.items.append(BillItem(
        category=line["category"], description=line["description"], quantity=line["quantity"],
        unit_price=line["unit_price"], amount=line["amount"],
        source_type=line.get("source_type"), source_id=line.get("source_id"), source_key=line.get("source_key"),
    ))


def other_service_lines(services):
    return [{"category": "other", "description": s["description"].strip(), "quantity": s.get("quantity", 1),
             "unit_price": money(s["unit_price"]), "amount": money(s["unit_price"]) * s.get("quantity", 1),
             "source_type": None, "source_id": None, "source_key": None} for s in services or []]


def generate_bill(patient, created_by_id, discount_percent=0, tax_percent=None, other_services=None):
    """Creates ONE bill containing every unbilled service. Returns the Bill, or None if there is nothing to bill."""
    if tax_percent is None:
        tax_percent = current_app.config["DEFAULT_TAX_PERCENT"]
    lines = collect_billable_items(patient) + other_service_lines(other_services)
    if not lines:
        return None

    # amount_paid is set explicitly: column defaults only apply at INSERT, but we calculate before saving.
    bill = Bill(bill_number=next_number(Bill, Bill.bill_number, "B"), patient_id=patient.id,
                discount_percent=money(discount_percent), tax_percent=money(tax_percent),
                amount_paid=Decimal("0"), created_by_id=created_by_id)
    for line in lines:
        _add_item(bill, line)
    recalculate(bill)
    db.session.add(bill)
    try:
        db.session.commit()
    except IntegrityError:
        # Someone else billed the same service a moment ago (UNIQUE source_key stopped us).
        db.session.rollback()
        return None
    return bill


def add_other_service(bill, service):
    _add_item(bill, other_service_lines([service])[0])
    recalculate(bill)
    db.session.commit()
    return bill


def adjust_bill(bill, discount_percent=None, tax_percent=None):
    if discount_percent is not None:
        bill.discount_percent = money(discount_percent)
    if tax_percent is not None:
        bill.tax_percent = money(tax_percent)
    recalculate(bill)
    db.session.commit()
    return bill


# ----------------------------------------------------------------------------
# Payments (multiple methods, partial payments, outstanding amount, receipts)
# ----------------------------------------------------------------------------

def record_payment(bill, amount, method, reference, received_by_id):
    """Returns (payment, error_message)."""
    # Lock the bill row so two cashiers cannot both pay the same outstanding amount.
    locked = db.session.query(Bill).filter_by(id=bill.id).with_for_update().one()
    amount = money(amount)
    if locked.outstanding <= 0:
        return None, "This bill is already fully paid"
    if amount > locked.outstanding:
        return None, f"Amount exceeds the outstanding balance of Rs. {locked.outstanding:.2f}"

    payment = Payment(receipt_number=next_number(Payment, Payment.receipt_number, "R"), bill_id=locked.id,
                      amount=amount, method=method, reference=(reference or None), received_by_id=received_by_id)
    db.session.add(payment)
    locked.amount_paid = Decimal(locked.amount_paid) + amount
    refresh_status(locked)
    db.session.commit()
    return payment, None


def balance_after(payment):
    """Bill balance right after this particular payment (for the receipt)."""
    bill = payment.bill
    paid_so_far = sum((Decimal(p.amount) for p in bill.payments if p.id <= payment.id), Decimal("0"))
    return Decimal(bill.total_amount) - paid_so_far


def search_bills(args):
    from app.models.patient import Patient
    q = Bill.query
    if args.get("patient_id"):
        q = q.filter(Bill.patient_id == int(args["patient_id"]))
    if args.get("patient_code"):
        q = q.join(Patient).filter(Patient.patient_code == args["patient_code"])
    if args.get("status"):
        q = q.filter(Bill.status == args["status"])
    return q.order_by(Bill.id.desc())
