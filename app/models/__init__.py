"""Import every model here so SQLAlchemy knows about all tables."""
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.patient import MedicalHistory, Patient, VisitHistory  # noqa: F401
from app.models.doctor import Department, Doctor, DoctorSchedule  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.bed import Admission, Bed, Ward  # noqa: F401
