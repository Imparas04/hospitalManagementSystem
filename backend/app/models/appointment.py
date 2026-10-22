from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


STATUS_SCHEDULED = "scheduled"
STATUS_WAITLISTED = "waitlisted"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_NO_SHOW = "no_show"
APPOINTMENT_STATUSES = (STATUS_SCHEDULED, STATUS_WAITLISTED, STATUS_COMPLETED, STATUS_CANCELLED, STATUS_NO_SHOW)


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)

    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=15)

    status = db.Column(db.String(20), nullable=False, default=STATUS_SCHEDULED)
    reason = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.String(500))

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    patient = db.relationship("Patient")
    doctor = db.relationship("Doctor")
    department = db.relationship("Department")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "patient_code": self.patient.patient_code if self.patient else None,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.user.full_name if self.doctor and self.doctor.user else None,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "appointment_time": self.appointment_time.strftime("%H:%M") if self.appointment_time else None,
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "reason": self.reason,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
