"""Import every model here so SQLAlchemy knows about all tables."""
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.patient import MedicalHistory, Patient, VisitHistory  # noqa: F401
from app.models.doctor import Department, Doctor, DoctorSchedule  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.bed import Admission, Bed, Ward  # noqa: F401
from app.models.triage import TriageRecord  # noqa: F401
from app.models.lab import LabOrder, LabResult, LabTest  # noqa: F401
from app.models.pharmacy import Medicine, MedicineBatch, Prescription, PrescriptionItem  # noqa: F401
from app.models.billing import Bill, BillItem, DischargeSummary, Payment  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.notification import Notification, NotificationRead  # noqa: F401
