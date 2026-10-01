"""Patient creation, unique Patient ID generation, search/filter query building."""
from datetime import date, datetime

from sqlalchemy import extract

from app.extensions import db
from app.models.patient import MedicalHistory, Patient, VisitHistory


def _parse_dob(value):
    """Accepts either a 'YYYY-MM-DD' string (from JSON) or an already-parsed date."""
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


def generate_patient_code():
    """P + year + 6-digit sequence, e.g. P2026000001. Resets the sequence each year.

    Uses a row lock (with_for_update) so two simultaneous registrations never get
    the same code, even under concurrent requests.
    """
    year = date.today().year
    prefix = f"P{year}"
    last = (
        Patient.query.filter(Patient.patient_code.like(f"{prefix}%"))
        .order_by(Patient.id.desc())
        .with_for_update()
        .first()
    )
    next_seq = int(last.patient_code[len(prefix):]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


def create_patient(data, created_by_id):
    is_emergency = bool(data.get("is_emergency_registration", False))
    patient = Patient(
        patient_code=generate_patient_code(),
        full_name=data["full_name"].strip(),
        date_of_birth=_parse_dob(data["date_of_birth"]),
        gender=data["gender"],
        blood_group=data.get("blood_group") or "unknown",
        phone=data["phone"].strip(),
        email=(data.get("email") or None),
        address=(data.get("address") or None),
        emergency_contact_name=(data.get("emergency_contact_name") or None),
        emergency_contact_phone=(data.get("emergency_contact_phone") or None),
        is_emergency_registration=is_emergency,
        # An emergency walk-in can be registered with minimal details; receptionist
        # completes the rest later and flips this off via PUT /patients/<id>.
        registration_pending=bool(data.get("registration_pending", is_emergency)),
        created_by_id=created_by_id,
    )
    db.session.add(patient)
    db.session.commit()
    return patient


def update_patient(patient, data):
    for field in ("full_name", "phone", "email", "address",
                  "emergency_contact_name", "emergency_contact_phone", "gender", "blood_group"):
        if field in data:
            value = data[field]
            patient.__setattr__(field, value.strip() if isinstance(value, str) and value else (value or None))
    if "date_of_birth" in data:
        patient.date_of_birth = _parse_dob(data["date_of_birth"])
    if "registration_pending" in data:
        patient.registration_pending = bool(data["registration_pending"])
    db.session.commit()
    return patient


def search_patients(query_params):
    """Builds the filtered/paginated Patient query used by GET /api/patients."""
    q = Patient.query

    is_active = query_params.get("is_active", "true")
    if is_active in ("true", "false"):
        q = q.filter(Patient.is_active == (is_active == "true"))

    search = (query_params.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(
            Patient.full_name.like(like),
            Patient.patient_code.like(like),
            Patient.phone.like(like),
        ))

    gender = query_params.get("gender")
    if gender:
        q = q.filter(Patient.gender == gender)

    blood_group = query_params.get("blood_group")
    if blood_group:
        q = q.filter(Patient.blood_group == blood_group)

    if query_params.get("emergency") == "true":
        q = q.filter(Patient.is_emergency_registration.is_(True))

    min_age, max_age = query_params.get("min_age"), query_params.get("max_age")
    this_year = date.today().year
    if min_age:
        q = q.filter((this_year - extract("year", Patient.date_of_birth)) >= int(min_age))
    if max_age:
        q = q.filter((this_year - extract("year", Patient.date_of_birth)) <= int(max_age))

    return q.order_by(Patient.id.desc())


def add_medical_history(patient, data, recorded_by_id):
    entry = MedicalHistory(
        patient_id=patient.id,
        condition_type=data["condition_type"],
        description=data["description"].strip(),
        recorded_by_id=recorded_by_id,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def add_visit(patient, data, recorded_by_id):
    visit = VisitHistory(
        patient_id=patient.id,
        visit_type=data["visit_type"],
        reason=data["reason"].strip(),
        notes=(data.get("notes") or None),
        recorded_by_id=recorded_by_id,
    )
    db.session.add(visit)
    db.session.commit()
    return visit
