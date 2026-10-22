from datetime import datetime, timezone

from app.extensions import db

# The 7 roles required by the project document.
ROLE_ADMIN = "admin"
ROLE_RECEPTIONIST = "receptionist"
ROLE_DOCTOR = "doctor"
ROLE_NURSE = "nurse"
ROLE_LAB_TECH = "lab_technician"
ROLE_PHARMACIST = "pharmacist"
ROLE_BILLING = "billing_staff"

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Full system access",
    ROLE_RECEPTIONIST: "Patients, appointments and admissions",
    ROLE_DOCTOR: "Patients, appointments, prescriptions and lab reports",
    ROLE_NURSE: "Patient care, bed allocation and vital signs",
    ROLE_LAB_TECH: "Lab tests, samples and results",
    ROLE_PHARMACIST: "Prescriptions and medicine inventory",
    ROLE_BILLING: "Bills, payments and receipts",
}

ALL_ROLES = list(ROLE_DESCRIPTIONS.keys())


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", back_populates="role")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}
