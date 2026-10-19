from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


LAB_STATUSES = ("ordered", "sample_collected", "processing", "result_entered", "reviewed")


class LabTest(db.Model):
    """Master catalog of test types a doctor can prescribe, e.g. CBC, LFT."""
    __tablename__ = "lab_tests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)   # e.g. CBC, LFT, KFT
    normal_range = db.Column(db.String(100))                        # reference text, e.g. "4.5-11.0 x10^9/L"
    price = db.Column(db.Numeric(10, 2), nullable=False, default=300)  # charged per test (Rs.)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code,
                "normal_range": self.normal_range, "price": float(self.price), "is_active": self.is_active}


class LabOrder(db.Model):
    """One prescribed test for one patient. Workflow:
    ordered -> sample_collected -> processing -> result_entered -> reviewed."""
    __tablename__ = "lab_orders"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    lab_test_id = db.Column(db.Integer, db.ForeignKey("lab_tests.id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="ordered")
    notes = db.Column(db.String(500))

    ordered_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    patient = db.relationship("Patient")
    doctor = db.relationship("Doctor")
    lab_test = db.relationship("LabTest")
    result = db.relationship("LabResult", back_populates="order", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "patient_code": self.patient.patient_code if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.user.full_name if self.doctor and self.doctor.user else None,
            "test_name": self.lab_test.name if self.lab_test else None,
            "test_code": self.lab_test.code if self.lab_test else None,
            "status": self.status,
            "notes": self.notes,
            "ordered_at": self.ordered_at.isoformat() if self.ordered_at else None,
            "result": self.result.to_dict() if self.result else None,
        }


class LabResult(db.Model):
    __tablename__ = "lab_results"

    id = db.Column(db.Integer, primary_key=True)
    lab_order_id = db.Column(db.Integer, db.ForeignKey("lab_orders.id"), unique=True, nullable=False)
    result_value = db.Column(db.String(500), nullable=False)
    is_abnormal = db.Column(db.Boolean, nullable=False, default=False)
    entered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    entered_at = db.Column(db.DateTime, nullable=False, default=_now)
    reviewer_notes = db.Column(db.String(500))
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)

    order = db.relationship("LabOrder", back_populates="result")

    def to_dict(self):
        return {
            "result_value": self.result_value,
            "is_abnormal": self.is_abnormal,
            "entered_at": self.entered_at.isoformat() if self.entered_at else None,
            "reviewer_notes": self.reviewer_notes,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }
