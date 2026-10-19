from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


BILL_UNPAID = "unpaid"
BILL_PARTIAL = "partially_paid"
BILL_PAID = "paid"

ITEM_CATEGORIES = ("consultation", "bed", "laboratory", "medicine", "other")
PAYMENT_METHODS = ("cash", "card", "upi", "bank_transfer", "insurance")


class Bill(db.Model):
    """One invoice for a patient. Totals are always recalculated from the items
    (see billing_service.recalculate), never typed in by hand."""
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(20), unique=True, nullable=False)   # e.g. B2026000001
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)

    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default=BILL_UNPAID, index=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    patient = db.relationship("Patient")
    items = db.relationship("BillItem", back_populates="bill", cascade="all, delete-orphan", order_by="BillItem.id")
    payments = db.relationship("Payment", back_populates="bill", order_by="Payment.id")

    @property
    def outstanding(self):
        return Decimal(self.total_amount) - Decimal(self.amount_paid)

    def to_dict(self, include_details=False):
        data = {
            "id": self.id,
            "bill_number": self.bill_number,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "patient_code": self.patient.patient_code if self.patient else None,
            "subtotal": float(self.subtotal),
            "discount_percent": float(self.discount_percent),
            "discount_amount": float(self.discount_amount),
            "tax_percent": float(self.tax_percent),
            "tax_amount": float(self.tax_amount),
            "total_amount": float(self.total_amount),
            "amount_paid": float(self.amount_paid),
            "outstanding_amount": float(self.outstanding),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_details:
            data["items"] = [i.to_dict() for i in self.items]
            data["payments"] = [p.to_dict() for p in self.payments]
        return data


class BillItem(db.Model):
    """One line on a bill. source_type/source_id remember WHAT was billed, so the
    same appointment / lab order / admission / prescription quantity is never billed twice."""
    __tablename__ = "bill_items"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False)            # consultation|bed|laboratory|medicine|other
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)       # price at the time of billing (snapshot)
    amount = db.Column(db.Numeric(10, 2), nullable=False)           # quantity * unit_price

    source_type = db.Column(db.String(30))                          # appointment|lab_order|admission|prescription_item
    source_id = db.Column(db.Integer)
    # One-time sources get a unique key like "appointment:5" so the DATABASE itself blocks double billing.
    # Prescription items can be billed in several partial rounds, so they leave this NULL.
    source_key = db.Column(db.String(50), unique=True)

    bill = db.relationship("Bill", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id, "category": self.category, "description": self.description,
            "quantity": self.quantity, "unit_price": float(self.unit_price), "amount": float(self.amount),
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(20), unique=True, nullable=False)   # e.g. R2026000001
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(20), nullable=False)
    reference = db.Column(db.String(100))                                    # card slip no., UPI txn id, ...
    received_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False, default=_now)

    bill = db.relationship("Bill", back_populates="payments")
    received_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id, "receipt_number": self.receipt_number, "bill_id": self.bill_id,
            "amount": float(self.amount), "method": self.method, "reference": self.reference,
            "received_by": self.received_by.full_name if self.received_by else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


class DischargeSummary(db.Model):
    """The doctor's discharge note. Everything else on the printed summary
    (lab reports, medicines, final bill) is collected live from other tables."""
    __tablename__ = "discharge_summaries"

    id = db.Column(db.Integer, primary_key=True)
    admission_id = db.Column(db.Integer, db.ForeignKey("admissions.id"), unique=True, nullable=False)
    diagnosis = db.Column(db.String(500), nullable=False)
    treatment_summary = db.Column(db.String(2000), nullable=False)
    doctor_instructions = db.Column(db.String(1000))
    follow_up_date = db.Column(db.Date)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    admission = db.relationship("Admission")
