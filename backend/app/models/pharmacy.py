from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


PRESCRIPTION_STATUSES = ("pending", "partially_issued", "issued")


class Medicine(db.Model):
    """Master catalog of medicines (not stock - stock lives in MedicineBatch)."""
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    unit = db.Column(db.String(20), nullable=False)       # tablet | syrup | injection | ointment | drops
    reorder_level = db.Column(db.Integer, nullable=False, default=10)  # total stock below this = low-stock alert
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=10)  # selling price per unit (Rs.)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    batches = db.relationship("MedicineBatch", back_populates="medicine", cascade="all, delete-orphan")

    def to_dict(self):
        total_available = sum(b.available_quantity for b in self.batches if not b.is_expired)
        return {
            "id": self.id, "name": self.name, "unit": self.unit, "reorder_level": self.reorder_level,
            "unit_price": float(self.unit_price), "is_active": self.is_active,
            "total_available": total_available,
            "is_low_stock": total_available < self.reorder_level,
        }


class MedicineBatch(db.Model):
    """One purchased batch of a medicine - has its own expiry and remaining quantity."""
    __tablename__ = "medicine_stock"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False, index=True)
    batch_number = db.Column(db.String(50), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False, index=True)
    purchase_quantity = db.Column(db.Integer, nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    medicine = db.relationship("Medicine", back_populates="batches")

    __table_args__ = (db.UniqueConstraint("medicine_id", "batch_number", name="uq_medicine_batch_number"),)

    @property
    def is_expired(self):
        from datetime import date
        return self.expiry_date < date.today()

    def to_dict(self):
        return {
            "id": self.id, "batch_number": self.batch_number,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "purchase_quantity": self.purchase_quantity, "available_quantity": self.available_quantity,
            "is_expired": self.is_expired,
        }


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    notes = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    patient = db.relationship("Patient")
    doctor = db.relationship("Doctor")
    items = db.relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.user.full_name if self.doctor and self.doctor.user else None,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class PrescriptionItem(db.Model):
    __tablename__ = "prescription_items"

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)       # e.g. "1 tablet twice a day for 5 days"
    quantity_prescribed = db.Column(db.Integer, nullable=False)
    quantity_issued = db.Column(db.Integer, nullable=False, default=0)

    prescription = db.relationship("Prescription", back_populates="items")
    medicine = db.relationship("Medicine")

    @property
    def status(self):
        if self.quantity_issued == 0:
            return "pending"
        if self.quantity_issued < self.quantity_prescribed:
            return "partially_issued"
        return "issued"

    def to_dict(self):
        return {
            "id": self.id, "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.name if self.medicine else None,
            "dosage": self.dosage,
            "quantity_prescribed": self.quantity_prescribed,
            "quantity_issued": self.quantity_issued,
            "status": self.status,
        }
