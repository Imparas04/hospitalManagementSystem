"""Audit trail: records every important action automatically.

How it works (viva notes):
  Flask lets us run a function after every request (`after_request`). For each request that
  CHANGED something (POST / PUT / DELETE) and SUCCEEDED (2xx), we look the endpoint up in
  AUDIT_RULES below and write one row: who (user + role), what (action), on which record
  (entity + id), a readable description, when and from which IP.

Why a rule table and not a line of code inside every route?
  * all audit behaviour is in ONE file - easy to read, review and explain
  * existing routes and the API contract are unchanged
  * tests/test_audit.py FAILS if someone adds a new write endpoint without an audit rule,
    so coverage cannot silently rot.

Only successful actions are logged (a rejected request changed nothing), plus failed logins
(a security signal). Passwords are never logged.
"""
import re

from flask import g, request

from app.extensions import db
from app.services import audit_service


def S(data, *path, default="?"):
    """Safe nested lookup: S(d, "patient", "full_name") -> value or '?'  (never raises)."""
    for key in path:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    return default if data is None else data


class R:
    """One audit rule.
    action     machine-readable name, e.g. 'patient.create'
    entity     type of record touched, e.g. 'Patient'
    describe   fn(data, view_args, body) -> readable sentence ('data' = the API response's data)
    id_arg     take the entity id from this URL argument (e.g. 'patient_id'), otherwise from data['id']
    id_path    take the entity id from a nested path in data, e.g. ('payment', 'id')
    own_id     entity id = the logged-in user's own id
    when       optional fn(request) -> bool, to log only some requests"""
    def __init__(self, action, entity, describe, id_arg=None, id_path=None, own_id=False, when=None):
        self.action, self.entity, self.describe = action, entity, describe
        self.id_arg, self.id_path, self.own_id, self.when = id_arg, id_path, own_id, when


def _fields(body):
    keys = sorted(k for k in (body or {}) if "password" not in k)
    return ", ".join(keys) if keys else "-"


AUDIT_RULES = {
    # ---- account ----------------------------------------------------------------
    ("POST", "/api/auth/change-password"): R("auth.change_password", "User", lambda d, a, b: "Changed own password", own_id=True),
    ("POST", "/api/users"): R("user.create", "User", lambda d, a, b: f"Created user {S(d,'username')} with role {S(d,'role')}"),
    ("PUT", "/api/users/<int:user_id>"): R("user.update", "User", lambda d, a, b: f"Updated user {S(d,'username')} (fields: {_fields(b)})", id_arg="user_id"),
    ("DELETE", "/api/users/<int:user_id>"): R("user.deactivate", "User", lambda d, a, b: f"Deactivated user {S(d,'username')}", id_arg="user_id"),
    ("POST", "/api/users/<int:user_id>/reset-password"): R("user.reset_password", "User", lambda d, a, b: f"Reset password of user #{a.get('user_id')}", id_arg="user_id"),
    # ---- patients ---------------------------------------------------------------
    ("POST", "/api/patients"): R("patient.create", "Patient", lambda d, a, b: f"Registered patient {S(d,'patient_code')} ({S(d,'full_name')})"),
    ("PUT", "/api/patients/<int:patient_id>"): R("patient.update", "Patient", lambda d, a, b: f"Updated patient {S(d,'patient_code')} (fields: {_fields(b)})", id_arg="patient_id"),
    ("DELETE", "/api/patients/<int:patient_id>"): R("patient.deactivate", "Patient", lambda d, a, b: f"Deactivated patient {S(d,'patient_code')}", id_arg="patient_id"),
    ("POST", "/api/patients/<int:patient_id>/medical-history"): R("patient.medical_history_add", "Patient", lambda d, a, b: f"Added {S(d,'condition_type')} to medical history of patient #{a.get('patient_id')}", id_arg="patient_id"),
    ("POST", "/api/patients/<int:patient_id>/visits"): R("patient.visit_add", "Patient", lambda d, a, b: f"Recorded {S(d,'visit_type')} visit for patient #{a.get('patient_id')}", id_arg="patient_id"),
    # ---- departments / doctors --------------------------------------------------
    ("POST", "/api/departments"): R("department.create", "Department", lambda d, a, b: f"Created department {S(d,'name')}"),
    ("PUT", "/api/departments/<int:dept_id>"): R("department.update", "Department", lambda d, a, b: f"Updated department {S(d,'name')}", id_arg="dept_id"),
    ("POST", "/api/doctors"): R("doctor.create", "Doctor", lambda d, a, b: f"Created doctor profile for {S(d,'full_name')} ({S(d,'specialization')})"),
    ("PUT", "/api/doctors/<int:doctor_id>"): R("doctor.update", "Doctor", lambda d, a, b: f"Updated doctor {S(d,'full_name')} (fields: {_fields(b)})", id_arg="doctor_id"),
    ("POST", "/api/doctors/<int:doctor_id>/schedule"): R("doctor.schedule_add", "Doctor", lambda d, a, b: f"Added schedule for doctor #{a.get('doctor_id')}: day {S(d,'day_of_week')} {S(d,'start_time')}-{S(d,'end_time')}", id_arg="doctor_id"),
    # ---- appointments -----------------------------------------------------------
    ("POST", "/api/appointments"): R("appointment.book", "Appointment", lambda d, a, b: f"Booked appointment for {S(d,'patient_name')} with Dr. {S(d,'doctor_name')} on {S(d,'appointment_date')} {S(d,'appointment_time')} ({S(d,'status')})"),
    ("PUT", "/api/appointments/<int:appointment_id>"): R("appointment.update", "Appointment", lambda d, a, b: f"Updated appointment of {S(d,'patient_name')}: {S(d,'appointment_date')} {S(d,'appointment_time')}", id_arg="appointment_id"),
    ("POST", "/api/appointments/<int:appointment_id>/cancel"): R("appointment.cancel", "Appointment", lambda d, a, b: f"Cancelled appointment of {S(d,'patient_name')}", id_arg="appointment_id"),
    ("POST", "/api/appointments/<int:appointment_id>/complete"): R("appointment.complete", "Appointment", lambda d, a, b: f"Completed appointment of {S(d,'patient_name')}", id_arg="appointment_id"),
    ("POST", "/api/appointments/<int:appointment_id>/no-show"): R("appointment.no_show", "Appointment", lambda d, a, b: f"Marked {S(d,'patient_name')} as no-show", id_arg="appointment_id"),
    ("POST", "/api/appointments/<int:appointment_id>/promote"): R("appointment.promote", "Appointment", lambda d, a, b: f"Moved {S(d,'patient_name')} from waiting list to scheduled", id_arg="appointment_id"),
    # ---- wards / beds / admissions ----------------------------------------------
    ("POST", "/api/wards"): R("ward.create", "Ward", lambda d, a, b: f"Created ward {S(d,'name')} ({S(d,'ward_type')})"),
    ("POST", "/api/wards/<int:ward_id>/beds"): R("bed.create", "Bed", lambda d, a, b: f"Added bed {S(d,'bed_number')} to ward {S(d,'ward_name')}"),
    ("PUT", "/api/beds/<int:bed_id>"): R("bed.update_status", "Bed", lambda d, a, b: f"Set bed {S(d,'bed_number')} ({S(d,'ward_name')}) to {S(d,'status')}", id_arg="bed_id"),
    ("POST", "/api/admissions"): R("admission.create", "Admission", lambda d, a, b: f"Admitted {S(d,'patient_name')} to {S(d,'ward_name')}, bed {S(d,'bed_number')}"),
    ("POST", "/api/admissions/<int:admission_id>/discharge"): R("admission.discharge", "Admission", lambda d, a, b: f"Discharged {S(d,'patient_name')}, bed {S(d,'bed_number')} freed", id_arg="admission_id"),
    ("POST", "/api/discharge/<int:admission_id>"): R("discharge.create", "Admission", lambda d, a, b: f"Discharged {S(d,'patient','full_name')} with discharge summary (final bill {S(d,'final_bill','bill_number',default='none')})", id_arg="admission_id"),
    # ---- emergency / triage -----------------------------------------------------
    ("POST", "/api/triage"): R("triage.create", "TriageRecord", lambda d, a, b: f"Recorded triage for {S(d,'patient_name')}: priority {S(d,'priority_level')}"),
    ("PUT", "/api/triage/<int:triage_id>/status"): R("triage.update_status", "TriageRecord", lambda d, a, b: f"Set triage status of {S(d,'patient_name')} to {S(d,'status')}", id_arg="triage_id"),
    ("POST", "/api/triage/<int:triage_id>/allocate-bed"): R("triage.allocate_bed", "TriageRecord", lambda d, a, b: f"Auto-allocated bed {S(d,'admission','bed_number')} ({S(d,'admission','ward_name')}) to {S(d,'triage','patient_name')}", id_arg="triage_id"),
    ("POST", "/api/triage/<int:triage_id>/resolve"): R("triage.resolve", "TriageRecord", lambda d, a, b: f"Resolved emergency case of {S(d,'patient_name')}", id_arg="triage_id"),
    # ---- laboratory -------------------------------------------------------------
    ("POST", "/api/lab/tests"): R("lab_test.create", "LabTest", lambda d, a, b: f"Created lab test {S(d,'code')} ({S(d,'name')})"),
    ("POST", "/api/lab/orders"): R("lab_order.create", "LabOrder", lambda d, a, b: f"Ordered {S(d,'test_code')} for {S(d,'patient_name')}"),
    ("PUT", "/api/lab/orders/<int:order_id>/status"): R("lab_order.update_status", "LabOrder", lambda d, a, b: f"Lab order for {S(d,'patient_name')} is now {S(d,'status')}", id_arg="order_id"),
    ("POST", "/api/lab/orders/<int:order_id>/result"): R("lab_order.result_entered", "LabOrder", lambda d, a, b: f"Entered {S(d,'test_code')} result for {S(d,'patient_name')}" + (" (ABNORMAL)" if S(d,'result','is_abnormal',default=False) is True else ""), id_arg="order_id"),
    ("POST", "/api/lab/orders/<int:order_id>/review"): R("lab_order.reviewed", "LabOrder", lambda d, a, b: f"Reviewed {S(d,'test_code')} result of {S(d,'patient_name')}", id_arg="order_id"),
    # ---- pharmacy ---------------------------------------------------------------
    ("POST", "/api/pharmacy/medicines"): R("medicine.create", "Medicine", lambda d, a, b: f"Created medicine {S(d,'name')}"),
    ("POST", "/api/pharmacy/medicines/<int:medicine_id>/batches"): R("medicine.batch_add", "Medicine", lambda d, a, b: f"Added batch {S(d,'batch_number')}: {S(d,'purchase_quantity')} units, expires {S(d,'expiry_date')}", id_arg="medicine_id"),
    ("POST", "/api/prescriptions"): R("prescription.create", "Prescription", lambda d, a, b: f"Prescribed {len(d.get('items', [])) if isinstance(d, dict) else '?'} medicine(s) to {S(d,'patient_name')}"),
    ("POST", "/api/prescriptions/<int:prescription_id>/issue"): R("prescription.issue", "Prescription", lambda d, a, b: f"Issued prescription #{a.get('prescription_id')} for {S(d,'prescription','patient_name')}: now {S(d,'prescription','status')}", id_arg="prescription_id"),
    # ---- billing ----------------------------------------------------------------
    ("POST", "/api/bills"): R("bill.create", "Bill", lambda d, a, b: f"Generated bill {S(d,'bill_number')} for {S(d,'patient_name')}: Rs. {S(d,'total_amount')}"),
    ("POST", "/api/bills/<int:bill_id>/items"): R("bill.add_item", "Bill", lambda d, a, b: f"Added service '{(b or {}).get('description', '?')}' to bill {S(d,'bill_number')}", id_arg="bill_id"),
    ("PUT", "/api/bills/<int:bill_id>/adjust"): R("bill.adjust", "Bill", lambda d, a, b: f"Adjusted bill {S(d,'bill_number')}: discount {S(d,'discount_percent')}%, tax {S(d,'tax_percent')}%", id_arg="bill_id"),
    ("POST", "/api/bills/<int:bill_id>/payments"): R("payment.create", "Payment", lambda d, a, b: f"Received Rs. {S(d,'payment','amount')} by {S(d,'payment','method')} for bill {S(d,'bill','bill_number')} (receipt {S(d,'payment','receipt_number')})", id_path=("payment", "id")),
    # ---- exporting data (sensitive: leaves the system) ---------------------------
    ("GET", "/api/reports/<report_type>"): R("report.export", "Report", lambda d, a, b: f"Exported {a.get('report_type')} report as {request.args.get('format')}", when=lambda r: r.args.get("format", "json") != "json"),
}

# Write endpoints that deliberately have NO audit rule (the test checks this list too).
AUDIT_EXEMPT = {
    ("POST", "/api/auth/login"),                          # handled separately below (success + failure)
    ("POST", "/api/notifications/<int:notification_id>/read"),   # a read-receipt, not a business action
    ("POST", "/api/notifications/read-all"),
    ("POST", "/api/notifications/refresh"),               # re-checks alerts, changes no business data
}


def _entity_id(rule, data, user):
    if rule.own_id:
        return user.id
    if rule.id_arg:
        return (request.view_args or {}).get(rule.id_arg)
    if rule.id_path:
        return S(data, *rule.id_path, default=None)
    return data.get("id") if isinstance(data, dict) else None


def _log_login(response):
    body = request.get_json(silent=True) or {}
    if response.status_code == 200:
        data = (response.get_json(silent=True) or {}).get("data") or {}
        user = data.get("user") or {}
        audit_service.record("auth.login", f"{user.get('username')} logged in", user_id=user.get("id"),
                             username=user.get("username"), role=user.get("role"),
                             entity_type="User", entity_id=user.get("id"))
    elif response.status_code == 401:
        attempted = re.sub(r"[\x00-\x1f]", " ", str(body.get("username") or ""))[:50]
        audit_service.record("auth.login_failed", f"Failed login attempt for username '{attempted}'",
                             username=attempted or None)


def _maybe_log(response):
    if request.url_rule is None:
        return
    key = (request.method, request.url_rule.rule)
    if key == ("POST", "/api/auth/login"):
        return _log_login(response)
    rule = AUDIT_RULES.get(key)
    if rule is None or not 200 <= response.status_code < 300:
        return
    if rule.when and not rule.when(request):
        return
    user = g.get("current_user")
    if user is None:
        return
    data = (response.get_json(silent=True) or {}).get("data") if response.is_json else None
    try:
        description = rule.describe(data, request.view_args or {}, request.get_json(silent=True) or {})
    except Exception:  # a description problem must never lose the audit entry itself
        description = f"{request.method} {request.path}"
    audit_service.record(rule.action, description, user=user, entity_type=rule.entity,
                         entity_id=_entity_id(rule, data, user))


def register_audit(app):
    @app.after_request
    def audit_after_request(response):
        try:
            _maybe_log(response)
        except Exception:
            # Auditing must never break the real request, which has already succeeded.
            app.logger.exception("Audit logging failed")
            db.session.rollback()
        return response
