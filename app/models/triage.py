from datetime import datetime, timezone

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
# Higher number = more urgent. Used to sort the emergency queue.
PRIORITY_RANK = {PRIORITY_CRITICAL: 4, PRIORITY_HIGH: 3, PRIORITY_MEDIUM: 2, PRIORITY_LOW: 1}

STATUS_WAITING = "waiting"
STATUS_BED_ASSIGNED = "bed_assigned"
STATUS_IN_TREATMENT = "in_treatment"
STATUS_RESOLVED = "resolved"
TRIAGE_STATUSES = (STATUS_WAITING, STATUS_BED_ASSIGNED, STATUS_IN_TREATMENT, STATUS_RESOLVED)


class TriageRecord(db.Model):
    """One emergency/triage assessment for a patient: vitals in, priority out."""
    __tablename__ = "triage_records"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)

    blood_pressure_systolic = db.Column(db.Integer, nullable=False)
    blood_pressure_diastolic = db.Column(db.Integer, nullable=False)
    heart_rate = db.Column(db.Integer, nullable=False)        # beats per minute
    oxygen_level = db.Column(db.Integer, nullable=False)      # SpO2 %
    temperature = db.Column(db.Float, nullable=False)         # Fahrenheit
    symptoms = db.Column(db.String(500), nullable=False)
    emergency_condition = db.Column(db.String(255))           # short label, e.g. "Road accident"

    icu_required = db.Column(db.Boolean, nullable=False, default=False)
    isolation_required = db.Column(db.Boolean, nullable=False, default=False)

    priority_level = db.Column(db.String(10), nullable=False)   # critical|high|medium|low - computed
    priority_score = db.Column(db.Integer, nullable=False)      # raw score the level was computed from
    status = db.Column(db.String(20), nullable=False, default=STATUS_WAITING)

    admission_id = db.Column(db.Integer, db.ForeignKey("admissions.id"))  # set once a bed is allocated

    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    patient = db.relationship("Patient")
    admission = db.relationship("Admission")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.full_name if self.patient else None,
            "patient_code": self.patient.patient_code if self.patient else None,
            "gender": self.patient.gender if self.patient else None,
            "vitals": {
                "blood_pressure": f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}",
                "heart_rate": self.heart_rate,
                "oxygen_level": self.oxygen_level,
                "temperature": self.temperature,
            },
            "symptoms": self.symptoms,
            "emergency_condition": self.emergency_condition,
            "icu_required": self.icu_required,
            "isolation_required": self.isolation_required,
            "priority_level": self.priority_level,
            "priority_score": self.priority_score,
            "status": self.status,
            "admission_id": self.admission_id,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
