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


def _check_money(data, field, errors, label):
    """Optional money field: a number >= 0 with at most 2 decimal places."""
    if field not in data:
        return
    val = data[field]
    if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0 or round(val, 2) != val:
        errors[field] = f"{label} must be a number >= 0 with at most 2 decimal places"


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
    _check_money(data, "consultation_fee", errors, "consultation_fee")
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
    gr = data.get("gender_restriction")
    if gr not in (None, "", "male", "female"):
        errors["gender_restriction"] = "gender_restriction must be 'male', 'female', or omitted (mixed ward)"
    _check_money(data, "daily_charge", errors, "daily_charge")
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


def validate_triage_payload(data):
    errors = {}

    def need_int(field, lo, hi, label):
        val = data.get(field)
        if not isinstance(val, int) or not lo <= val <= hi:
            errors[field] = f"{label} is required and must be a whole number between {lo} and {hi}"

    if not isinstance(data.get("patient_id"), int):
        errors["patient_id"] = "patient_id is required"
    need_int("blood_pressure_systolic", 40, 300, "Systolic BP")
    need_int("blood_pressure_diastolic", 20, 200, "Diastolic BP")
    need_int("heart_rate", 20, 250, "Heart rate")
    need_int("oxygen_level", 0, 100, "Oxygen level")

    temp = data.get("temperature")
    if not isinstance(temp, (int, float)) or not 85 <= temp <= 115:
        errors["temperature"] = "temperature is required and must be between 85 and 115 (Fahrenheit)"

    symptoms = data.get("symptoms")
    if not isinstance(symptoms, str) or not 2 <= len(symptoms.strip()) <= 500:
        errors["symptoms"] = "symptoms is required (2-500 characters)"

    for field in ("icu_required", "isolation_required"):
        if field in data and not isinstance(data[field], bool):
            errors[field] = f"{field} must be true or false"
    return errors


def validate_triage_status_payload(data):
    from app.models.triage import TRIAGE_STATUSES
    errors = {}
    if data.get("status") not in TRIAGE_STATUSES:
        errors["status"] = f"status must be one of: {', '.join(TRIAGE_STATUSES)}"
    return errors


def validate_lab_test_payload(data):
    errors = {}
    if not (isinstance(data.get("name"), str) and data["name"].strip()):
        errors["name"] = "name is required"
    if not (isinstance(data.get("code"), str) and 1 <= len(data["code"].strip()) <= 20):
        errors["code"] = "code is required (max 20 characters)"
    _check_money(data, "price", errors, "price")
    return errors


def validate_lab_order_payload(data):
    errors = {}
    if not isinstance(data.get("patient_id"), int):
        errors["patient_id"] = "patient_id is required"
    if not isinstance(data.get("lab_test_id"), int):
        errors["lab_test_id"] = "lab_test_id is required"
    return errors


def validate_lab_status_payload(data):
    from app.models.lab import LAB_STATUSES
    errors = {}
    if data.get("status") not in LAB_STATUSES:
        errors["status"] = f"status must be one of: {', '.join(LAB_STATUSES)}"
    return errors


def validate_lab_result_payload(data):
    errors = {}
    val = data.get("result_value")
    if not isinstance(val, str) or not 1 <= len(val.strip()) <= 500:
        errors["result_value"] = "result_value is required (max 500 characters)"
    if "is_abnormal" in data and not isinstance(data["is_abnormal"], bool):
        errors["is_abnormal"] = "is_abnormal must be true or false"
    return errors


def validate_medicine_payload(data):
    errors = {}
    units = ("tablet", "syrup", "injection", "ointment", "drops")
    if not (isinstance(data.get("name"), str) and data["name"].strip()):
        errors["name"] = "name is required"
    if data.get("unit") not in units:
        errors["unit"] = f"unit must be one of: {', '.join(units)}"
    level = data.get("reorder_level", 10)
    if not isinstance(level, int) or level < 0:
        errors["reorder_level"] = "reorder_level must be a non-negative whole number"
    _check_money(data, "unit_price", errors, "unit_price")
    return errors


def validate_batch_payload(data):
    import datetime as _dt
    errors = {}
    if not (isinstance(data.get("batch_number"), str) and data["batch_number"].strip()):
        errors["batch_number"] = "batch_number is required"
    try:
        expiry = _dt.datetime.strptime(data.get("expiry_date", ""), "%Y-%m-%d").date()
        if expiry <= _dt.date.today():
            errors["expiry_date"] = "expiry_date must be in the future"
    except (ValueError, TypeError):
        errors["expiry_date"] = "expiry_date is required, format YYYY-MM-DD"
    qty = data.get("purchase_quantity")
    if not isinstance(qty, int) or qty <= 0:
        errors["purchase_quantity"] = "purchase_quantity must be a positive whole number"
    return errors


def validate_prescription_payload(data):
    errors = {}
    if not isinstance(data.get("patient_id"), int):
        errors["patient_id"] = "patient_id is required"
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors["items"] = "items is required and must be a non-empty list"
    else:
        item_errors = []
        for item in items:
            e = {}
            if not isinstance(item.get("medicine_id"), int):
                e["medicine_id"] = "medicine_id is required"
            if not (isinstance(item.get("dosage"), str) and item["dosage"].strip()):
                e["dosage"] = "dosage is required"
            qty = item.get("quantity")
            if not isinstance(qty, int) or qty <= 0:
                e["quantity"] = "quantity must be a positive whole number"
            item_errors.append(e)
        if any(item_errors):
            errors["items"] = item_errors
    return errors


def _check_percent(data, field, errors, label):
    if field not in data:
        return
    val = data[field]
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not 0 <= val <= 100 or round(val, 2) != val:
        errors[field] = f"{label} must be a number between 0 and 100 (max 2 decimal places)"


def validate_other_service(item):
    errors = {}
    if not (isinstance(item.get("description"), str) and 2 <= len(item["description"].strip()) <= 255):
        errors["description"] = "description is required (2-255 characters)"
    qty = item.get("quantity", 1)
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        errors["quantity"] = "quantity must be a positive whole number"
    if "unit_price" not in item:
        errors["unit_price"] = "unit_price is required"
    else:
        _check_money(item, "unit_price", errors, "unit_price")
    return errors


def validate_bill_payload(data):
    errors = {}
    pid, code = data.get("patient_id"), data.get("patient_code")
    if pid is None and code is None:
        errors["patient_id"] = "patient_id or patient_code is required"
    elif pid is not None and (isinstance(pid, bool) or not isinstance(pid, int)):
        errors["patient_id"] = "patient_id must be a number"
    elif code is not None and not isinstance(code, str):
        errors["patient_code"] = "patient_code must be text"
    _check_percent(data, "discount_percent", errors, "discount_percent")
    _check_percent(data, "tax_percent", errors, "tax_percent")
    services = data.get("other_services")
    if services is not None:
        if not isinstance(services, list):
            errors["other_services"] = "other_services must be a list"
        else:
            svc_errors = [validate_other_service(s) if isinstance(s, dict) else {"item": "must be an object"} for s in services]
            if any(svc_errors):
                errors["other_services"] = svc_errors
    return errors


def validate_adjust_payload(data):
    errors = {}
    if "discount_percent" not in data and "tax_percent" not in data:
        errors["body"] = "Send discount_percent and/or tax_percent"
    _check_percent(data, "discount_percent", errors, "discount_percent")
    _check_percent(data, "tax_percent", errors, "tax_percent")
    return errors


def validate_payment_payload(data):
    from app.models.billing import PAYMENT_METHODS
    errors = {}
    amount = data.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0 or round(amount, 2) != amount:
        errors["amount"] = "amount is required: a number greater than 0 with at most 2 decimal places"
    if data.get("method") not in PAYMENT_METHODS:
        errors["method"] = f"method must be one of: {', '.join(PAYMENT_METHODS)}"
    ref = data.get("reference")
    if ref is not None and (not isinstance(ref, str) or len(ref) > 100):
        errors["reference"] = "reference must be text up to 100 characters"
    return errors


def validate_discharge_payload(data):
    import datetime as _dt
    errors = {}
    diagnosis = data.get("diagnosis")
    if not isinstance(diagnosis, str) or not 2 <= len(diagnosis.strip()) <= 500:
        errors["diagnosis"] = "diagnosis is required (2-500 characters)"
    treatment = data.get("treatment_summary")
    if not isinstance(treatment, str) or not 2 <= len(treatment.strip()) <= 2000:
        errors["treatment_summary"] = "treatment_summary is required (2-2000 characters)"
    instr = data.get("doctor_instructions")
    if instr is not None and (not isinstance(instr, str) or len(instr) > 1000):
        errors["doctor_instructions"] = "doctor_instructions must be text up to 1000 characters"
    fu = data.get("follow_up_date")
    if fu not in (None, ""):
        try:
            if _dt.datetime.strptime(fu, "%Y-%m-%d").date() < _dt.date.today():
                errors["follow_up_date"] = "follow_up_date cannot be in the past"
        except (ValueError, TypeError):
            errors["follow_up_date"] = "follow_up_date must be in format YYYY-MM-DD"
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
