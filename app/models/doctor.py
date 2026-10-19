from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    doctors = db.relationship("Doctor", back_populates="department")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description, "is_active": self.is_active}


class Doctor(db.Model):
    """Extra profile data for a User whose role is 'doctor'. One doctor row per user."""
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    is_on_emergency_duty = db.Column(db.Boolean, nullable=False, default=False)
    consultation_fee = db.Column(db.Numeric(10, 2), nullable=False, default=500)  # charged per completed appointment (Rs.)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    user = db.relationship("User")
    department = db.relationship("Department", back_populates="doctors")
    schedules = db.relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.user.full_name if self.user else None,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "specialization": self.specialization,
            "is_on_emergency_duty": self.is_on_emergency_duty,
            "consultation_fee": float(self.consultation_fee),
            "is_active": self.is_active,
        }


# 0 = Monday ... 6 = Sunday (Python's date.weekday() convention)
class DoctorSchedule(db.Model):
    """One row = 'this doctor is available on this weekday between start_time and end_time'."""
    __tablename__ = "doctor_schedules"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False, default=15)

    doctor = db.relationship("Doctor", back_populates="schedules")

    def to_dict(self):
        return {
            "id": self.id,
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "slot_minutes": self.slot_minutes,
        }
