"""Small, readable input validation helpers.

Each validator returns a dict of {field: error_message}. Empty dict = valid.
"""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,50}$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def validate_password(password):
    """Min 8 chars, at least one letter and one digit. Returns error text or None."""
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password is too long (max 128 characters)"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must contain at least one letter and one digit"
    return None


def validate_patient_payload(data, partial=False):
    """Validate the body for creating (partial=False) or updating (partial=True) a patient."""
    from datetime import date, datetime

    from app.models.patient import BLOOD_GROUP_CHOICES, GENDER_CHOICES

    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    if missing("full_name"):
        errors["full_name"] = "Full name is required"
    elif "full_name" in data and (not isinstance(data["full_name"], str) or not 2 <= len(data["full_name"].strip()) <= 100):
        errors["full_name"] = "Full name must be 2-100 characters"

    if missing("date_of_birth"):
        errors["date_of_birth"] = "Date of birth is required (format: YYYY-MM-DD)"
    elif "date_of_birth" in data:
        try:
            dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            if dob > date.today():
                errors["date_of_birth"] = "Date of birth cannot be in the future"
            elif dob.year < date.today().year - 130:
                errors["date_of_birth"] = "Date of birth is not realistic"
        except (ValueError, TypeError):
            errors["date_of_birth"] = "Date of birth must be in format YYYY-MM-DD"

    if missing("gender"):
        errors["gender"] = "Gender is required"
    elif "gender" in data and data["gender"] not in GENDER_CHOICES:
        errors["gender"] = f"Gender must be one of: {', '.join(GENDER_CHOICES)}"

    if "blood_group" in data and data["blood_group"] not in (None, "") and data["blood_group"] not in BLOOD_GROUP_CHOICES:
        errors["blood_group"] = f"Blood group must be one of: {', '.join(BLOOD_GROUP_CHOICES)}"

    if missing("phone"):
        errors["phone"] = "Phone is required"
    elif "phone" in data and (not isinstance(data["phone"], str) or not PHONE_RE.match(data["phone"])):
        errors["phone"] = "Phone must be 7-15 digits (optional leading +)"

    if data.get("email") not in (None, ""):
        if not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"]):
            errors["email"] = "Enter a valid email address"

    if data.get("emergency_contact_phone") not in (None, ""):
        if not PHONE_RE.match(data["emergency_contact_phone"]):
            errors["emergency_contact_phone"] = "Emergency contact phone must be 7-15 digits (optional leading +)"

    if "is_emergency_registration" in data and not isinstance(data["is_emergency_registration"], bool):
        errors["is_emergency_registration"] = "is_emergency_registration must be true or false"

    return errors


def validate_medical_history_payload(data):
    errors = {}
    valid_types = ("allergy", "chronic_condition", "surgery", "note")
    if data.get("condition_type") not in valid_types:
        errors["condition_type"] = f"condition_type must be one of: {', '.join(valid_types)}"
    desc = data.get("description")
    if not isinstance(desc, str) or not 2 <= len(desc.strip()) <= 500:
        errors["description"] = "description is required (2-500 characters)"
    return errors


def validate_visit_payload(data):
    errors = {}
    valid_types = ("opd", "emergency", "follow_up")
    if data.get("visit_type") not in valid_types:
        errors["visit_type"] = f"visit_type must be one of: {', '.join(valid_types)}"
    reason = data.get("reason")
    if not isinstance(reason, str) or not 2 <= len(reason.strip()) <= 255:
        errors["reason"] = "reason is required (2-255 characters)"
    return errors


def _is_hhmm(value):
    try:
        import datetime as _dt
        _dt.datetime.strptime(value, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def _is_yyyymmdd(value):
    try:
        import datetime as _dt
        _dt.datetime.strptime(value, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validate_department_payload(data, partial=False):
    errors = {}
    if not partial and not (isinstance(data.get("name"), str) and data["name"].strip()):
        errors["name"] = "Department name is required"
    elif "name" in data and (not isinstance(data["name"], str) or not 2 <= len(data["name"].strip()) <= 100):
        errors["name"] = "Department name must be 2-100 characters"
    if "is_active" in data and not isinstance(data["is_active"], bool):
        errors["is_active"] = "is_active must be true or false"
    return errors


def validate_doctor_payload(data, partial=False):
    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    if missing("user_id"):
        errors["user_id"] = "user_id is required"
    elif "user_id" in data and not isinstance(data["user_id"], int):
        errors["user_id"] = "user_id must be a number"

    if missing("department_id"):
        errors["department_id"] = "department_id is required"
    elif "department_id" in data and not isinstance(data["department_id"], int):
        errors["department_id"] = "department_id must be a number"

    if missing("specialization"):
        errors["specialization"] = "specialization is required"
    elif "specialization" in data and (not isinstance(data["specialization"], str) or not data["specialization"].strip()):
        errors["specialization"] = "specialization must not be empty"

    if "is_on_emergency_duty" in data and not isinstance(data["is_on_emergency_duty"], bool):
        errors["is_on_emergency_duty"] = "is_on_emergency_duty must be true or false"
    if "is_active" in data and not isinstance(data["is_active"], bool):
        errors["is_active"] = "is_active must be true or false"
    return errors


def validate_schedule_payload(data):
    errors = {}
    day = data.get("day_of_week")
    if not isinstance(day, int) or not 0 <= day <= 6:
        errors["day_of_week"] = "day_of_week must be 0 (Monday) to 6 (Sunday)"
    if not _is_hhmm(data.get("start_time")):
        errors["start_time"] = "start_time must be in format HH:MM"
    if not _is_hhmm(data.get("end_time")):
        errors["end_time"] = "end_time must be in format HH:MM"
    if "start_time" not in errors and "end_time" not in errors and data["start_time"] >= data["end_time"]:
        errors["end_time"] = "end_time must be after start_time"
    slot = data.get("slot_minutes", 15)
    if not isinstance(slot, int) or not 5 <= slot <= 120:
        errors["slot_minutes"] = "slot_minutes must be a number between 5 and 120"
    return errors


def validate_appointment_payload(data, partial=False):
    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    for field, label in (("patient_id", "patient_id"), ("doctor_id", "doctor_id")):
        if missing(field):
            errors[field] = f"{label} is required"
        elif field in data and not isinstance(data[field], int):
            errors[field] = f"{label} must be a number"

    if missing("appointment_date"):
        errors["appointment_date"] = "appointment_date is required (format YYYY-MM-DD)"
    elif "appointment_date" in data and not _is_yyyymmdd(data["appointment_date"]):
        errors["appointment_date"] = "appointment_date must be in format YYYY-MM-DD"

    if missing("appointment_time"):
        errors["appointment_time"] = "appointment_time is required (format HH:MM)"
    elif "appointment_time" in data and not _is_hhmm(data["appointment_time"]):
        errors["appointment_time"] = "appointment_time must be in format HH:MM"

    if missing("reason"):
        errors["reason"] = "reason is required"
    elif "reason" in data and (not isinstance(data["reason"], str) or not 2 <= len(data["reason"].strip()) <= 255):
        errors["reason"] = "reason must be 2-255 characters"

    if "allow_waitlist" in data and not isinstance(data["allow_waitlist"], bool):
        errors["allow_waitlist"] = "allow_waitlist must be true or false"
    return errors


def validate_ward_payload(data):
    from app.models.bed import WARD_TYPES
    errors = {}
    if not (isinstance(data.get("name"), str) and data["name"].strip()):
        errors["name"] = "Ward name is required"
    if data.get("ward_type") not in WARD_TYPES:
        errors["ward_type"] = f"ward_type must be one of: {', '.join(WARD_TYPES)}"
    return errors


def validate_bed_payload(data):
    from app.models.bed import BED_TYPES
    errors = {}
    if not (isinstance(data.get("bed_number"), str) and data["bed_number"].strip()):
        errors["bed_number"] = "bed_number is required"
    if data.get("bed_type") not in BED_TYPES:
        errors["bed_type"] = f"bed_type must be one of: {', '.join(BED_TYPES)}"
    return errors


def validate_admission_payload(data):
    errors = {}
    for field in ("patient_id", "bed_id", "doctor_id"):
        if not isinstance(data.get(field), int):
            errors[field] = f"{field} is required and must be a number"
    reason = data.get("reason")
    if not isinstance(reason, str) or not 2 <= len(reason.strip()) <= 255:
        errors["reason"] = "reason is required (2-255 characters)"
    return errors


def validate_user_payload(data, valid_roles, partial=False):
    """Validate the body for creating (partial=False) or updating (partial=True) a user."""
    errors = {}

    def missing(field):
        return not partial and (field not in data or data[field] in (None, ""))

    # username
    if missing("username"):
        errors["username"] = "Username is required"
    elif "username" in data and not USERNAME_RE.match(str(data["username"])):
        errors["username"] = "Username must be 3-50 characters: letters, digits, '_' or '.'"

    # email
    if missing("email"):
        errors["email"] = "Email is required"
    elif "email" in data and (not isinstance(data["email"], str) or not EMAIL_RE.match(data["email"])):
        errors["email"] = "Enter a valid email address"

    # full name
    if missing("full_name"):
        errors["full_name"] = "Full name is required"
    elif "full_name" in data and (not isinstance(data["full_name"], str) or not 2 <= len(data["full_name"].strip()) <= 100):
        errors["full_name"] = "Full name must be 2-100 characters"

    # role
    if missing("role"):
        errors["role"] = "Role is required"
    elif "role" in data and data["role"] not in valid_roles:
        errors["role"] = f"Role must be one of: {', '.join(valid_roles)}"

    # phone (optional)
    if data.get("phone") not in (None, ""):
        if not isinstance(data["phone"], str) or not PHONE_RE.match(data["phone"]):
            errors["phone"] = "Phone must be 7-15 digits (optional leading +)"

    # password (only when creating)
    if not partial:
        pw_error = validate_password(data.get("password"))
        if pw_error:
            errors["password"] = pw_error

    return errors
