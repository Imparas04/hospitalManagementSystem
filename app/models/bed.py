from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


WARD_TYPES = ("general", "icu", "isolation", "maternity", "pediatric")
BED_TYPES = ("general", "icu", "isolation")
BED_STATUSES = ("available", "occupied", "maintenance")
ADMISSION_STATUSES = ("admitted", "discharged")


class Ward(db.Model):
    __tablename__ = "wards"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    ward_type = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    beds = db.relationship("Bed", back_populates="ward", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "ward_type": self.ward_type, "is_active": self.is_active,
            "total_beds": len(self.beds),
            "available_beds": sum(1 for b in self.beds if b.status == "available"),
        }


class Bed(db.Model):
    __tablename__ = "beds"

    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.Integer, db.ForeignKey("wards.id"), nullable=False, index=True)
    bed_number = db.Column(db.String(20), nullable=False)
    bed_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="available")

    ward = db.relationship("Ward", back_populates="beds")

    __table_args__ = (db.UniqueConstraint("ward_id", "bed_number", name="uq_ward_bed_number"),)

    def to_dict(self):
        return {
            "id": self.id, "ward_id": self.ward_id, "ward_name": self.ward.name if self.ward else None,
            "bed_number": self.bed_number, "bed_type": self.bed_type, "status": self.status,
        }


class Admission(db.Model):
    __tablename__ = "admissions"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    bed_id = db.Column(db.Integer, db.ForeignKey("beds.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)

    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="admitted")
    admission_date = db.Column(db.DateTime, nullable=False, default=_now)
    discharge_date = db.Column(db.DateTime)

    admitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    patient = db.relationship("Patient")
    bed = db.relationship("Bed")
    doctor = db.relationship("Doctor")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "patient_code": self.patient.patient_code if self.patient else None,
            "bed_id": self.bed_id,
            "bed_number": self.bed.bed_number if self.bed else None,
            "ward_name": self.bed.ward.name if self.bed and self.bed.ward else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.user.full_name if self.doctor and self.doctor.user else None,
            "reason": self.reason,
            "status": self.status,
            "admission_date": self.admission_date.isoformat() if self.admission_date else None,
            "discharge_date": self.discharge_date.isoformat() if self.discharge_date else None,
        }
