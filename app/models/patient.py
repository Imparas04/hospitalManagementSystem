from datetime import date, datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


GENDER_CHOICES = ("male", "female", "other")
BLOOD_GROUP_CHOICES = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown")


class Patient(db.Model):
    """A hospital patient. patient_code is the human-friendly ID (e.g. P000001)."""
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    patient_code = db.Column(db.String(20), unique=True, nullable=False, index=True)

    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    blood_group = db.Column(db.String(10), nullable=False, default="unknown")

    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))

    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))

    is_emergency_registration = db.Column(db.Boolean, nullable=False, default=False)
    # True until receptionist/nurse completes the full profile for a walk-in emergency case.
    registration_pending = db.Column(db.Boolean, nullable=False, default=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)  # soft delete

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    created_by = db.relationship("User")
    medical_history = db.relationship(
        "MedicalHistory", back_populates="patient",
        cascade="all, delete-orphan", order_by="MedicalHistory.recorded_at.desc()")
    visits = db.relationship(
        "VisitHistory", back_populates="patient",
        cascade="all, delete-orphan", order_by="VisitHistory.visit_date.desc()")

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years

    def to_dict(self, include_history=False):
        data = {
            "id": self.id,
            "patient_code": self.patient_code,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "gender": self.gender,
            "blood_group": self.blood_group,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "is_emergency_registration": self.is_emergency_registration,
            "registration_pending": self.registration_pending,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_history:
            data["medical_history"] = [h.to_dict() for h in self.medical_history]
            data["visits"] = [v.to_dict() for v in self.visits]
        return data


class MedicalHistory(db.Model):
    """Standing medical facts: allergies, chronic conditions, past surgeries, notes."""
    __tablename__ = "medical_history"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    condition_type = db.Column(db.String(30), nullable=False)  # allergy | chronic_condition | surgery | note
    description = db.Column(db.String(500), nullable=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=_now)

    patient = db.relationship("Patient", back_populates="medical_history")
    recorded_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "condition_type": self.condition_type,
            "description": self.description,
            "recorded_by": self.recorded_by.full_name if self.recorded_by else None,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class VisitHistory(db.Model):
    """One row per hospital visit (OPD visit, emergency visit, follow-up, ...).

    Phase 3+ will link this to a real Appointment/Admission once those tables exist;
    for now it is a simple standalone log so 'previous visit history' already works.
    """
    __tablename__ = "visit_history"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    visit_date = db.Column(db.DateTime, nullable=False, default=_now)
    visit_type = db.Column(db.String(20), nullable=False)  # opd | emergency | follow_up
    reason = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.String(500))
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    patient = db.relationship("Patient", back_populates="visits")
    recorded_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "visit_type": self.visit_type,
            "reason": self.reason,
            "notes": self.notes,
            "recorded_by": self.recorded_by.full_name if self.recorded_by else None,
        }
