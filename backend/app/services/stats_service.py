"""Dashboard numbers (one dashboard per role) and Chart.js-ready chart data.

Every chart function returns the SAME shape, so the frontend needs one small helper:
    {"title": "...", "chart_type": "line|bar|doughnut", "labels": [...],
     "datasets": [{"label": "...", "data": [...], "backgroundColor": "...", "borderColor": "..."}]}
which can be passed almost directly to `new Chart(ctx, {type, data: {labels, datasets}})`.

"Today" always means today in the HOSPITAL's timezone (see utils/timeutils.py).
"""
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from flask import current_app

from app.extensions import db
from app.models.appointment import STATUS_CANCELLED, STATUS_COMPLETED, STATUS_SCHEDULED, STATUS_WAITLISTED, Appointment
from app.models.bed import Admission, Bed, Ward
from app.models.billing import BILL_PAID, Bill, Payment
from app.models.doctor import Department, Doctor
from app.models.lab import LabOrder, LabResult, LabTest
from app.models.patient import Patient
from app.models.pharmacy import Medicine, MedicineBatch, Prescription, PrescriptionItem
from app.models.role import (
    ROLE_ADMIN, ROLE_BILLING, ROLE_DOCTOR, ROLE_LAB_TECH, ROLE_NURSE, ROLE_PHARMACIST, ROLE_RECEPTIONIST,
)
from app.models.triage import PRIORITY_RANK, TriageRecord
from app.services import pharmacy_service
from app.utils.timeutils import (
    add_months, date_range, day_bounds_utc, local_today, month_start, range_bounds_utc, to_local_date,
    utc_now_naive,
)

PENDING_LAB = ("ordered", "sample_collected", "processing")
ACTIVE_TRIAGE = ("waiting", "bed_assigned", "in_treatment")


def _n(query):
    return query.count()


def _money(value):
    return round(float(value or 0), 2)


# ============================================================================
# DASHBOARDS  (one per role)
# ============================================================================

def _card(key, label, value, fmt="number"):
    return {"key": key, "label": label, "value": value, "format": fmt}


def _beds_by_status():
    rows = db.session.query(Bed.status, db.func.count(Bed.id)).group_by(Bed.status).all()
    counts = {status: count for status, count in rows}
    return {s: counts.get(s, 0) for s in ("available", "occupied", "maintenance")}


def _revenue_between(start, end):
    return db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.paid_at >= start, Payment.paid_at < end).scalar()


def _today_appointments(today, doctor_id=None):
    q = Appointment.query.filter(Appointment.appointment_date == today, Appointment.status != STATUS_CANCELLED)
    return q.filter(Appointment.doctor_id == doctor_id) if doctor_id else q


def _admin(user, today):
    start, end = day_bounds_utc(today)
    beds = _beds_by_status()
    by_status = dict(db.session.query(Appointment.status, db.func.count(Appointment.id))
                     .filter(Appointment.appointment_date == today).group_by(Appointment.status).all())
    return [
        _card("total_patients", "Total Patients", _n(Patient.query.filter_by(is_active=True))),
        _card("today_appointments", "Today's Appointments", _n(_today_appointments(today))),
        _card("available_beds", "Available Beds", beds["available"]),
        _card("occupied_beds", "Occupied Beds", beds["occupied"]),
        _card("emergency_patients", "Emergency Patients", _n(TriageRecord.query.filter(TriageRecord.status.in_(ACTIVE_TRIAGE)))),
        _card("pending_lab_tests", "Pending Lab Tests", _n(LabOrder.query.filter(LabOrder.status.in_(PENDING_LAB)))),
        _card("low_stock_medicines", "Low Stock Medicines", len(pharmacy_service.low_stock_medicines())),
        _card("today_revenue", "Today's Revenue", _money(_revenue_between(start, end)), "currency"),
    ], {"today_appointments_by_status": {s: by_status.get(s, 0) for s in
                                         (STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED, "no_show", STATUS_WAITLISTED)}}


def _receptionist(user, today):
    start, end = day_bounds_utc(today)
    beds = _beds_by_status()
    return [
        _card("today_appointments", "Today's Appointments", _n(_today_appointments(today))),
        _card("waiting_list", "On Waiting List", _n(Appointment.query.filter_by(status=STATUS_WAITLISTED))),
        _card("patients_registered_today", "Patients Registered Today",
              _n(Patient.query.filter(Patient.created_at >= start, Patient.created_at < end))),
        _card("current_admissions", "Currently Admitted", _n(Admission.query.filter_by(status="admitted"))),
        _card("available_beds", "Available Beds", beds["available"]),
    ], {}


def _doctor(user, today):
    doctor = Doctor.query.filter_by(user_id=user.id).first()
    if doctor is None:
        zero = [("my_appointments_today", "My Appointments Today"), ("my_upcoming_appointments", "Upcoming (next 7 days)"),
                ("lab_results_to_review", "Lab Results To Review"), ("my_admitted_patients", "My Admitted Patients"),
                ("emergency_queue_waiting", "Emergency Queue")]
        return [_card(k, label, 0) for k, label in zero], {"note": "No doctor profile is linked to this account yet."}
    upcoming = Appointment.query.filter(
        Appointment.doctor_id == doctor.id, Appointment.status == STATUS_SCHEDULED,
        Appointment.appointment_date > today, Appointment.appointment_date <= today + timedelta(days=7))
    return [
        _card("my_appointments_today", "My Appointments Today", _n(_today_appointments(today, doctor.id))),
        _card("my_upcoming_appointments", "Upcoming (next 7 days)", _n(upcoming)),
        _card("lab_results_to_review", "Lab Results To Review",
              _n(LabOrder.query.filter_by(doctor_id=doctor.id, status="result_entered"))),
        _card("my_admitted_patients", "My Admitted Patients", _n(Admission.query.filter_by(doctor_id=doctor.id, status="admitted"))),
        _card("emergency_queue_waiting", "Emergency Queue", _n(TriageRecord.query.filter_by(status="waiting"))),
    ], {}


def _nurse(user, today):
    beds = _beds_by_status()
    waiting = TriageRecord.query.filter_by(status="waiting")
    return [
        _card("emergency_waiting", "Emergency Queue", _n(waiting)),
        _card("critical_waiting", "Critical Patients Waiting", _n(waiting.filter_by(priority_level="critical"))),
        _card("admitted_patients", "Admitted Patients", _n(Admission.query.filter_by(status="admitted"))),
        _card("available_beds", "Available Beds", beds["available"]),
        _card("occupied_beds", "Occupied Beds", beds["occupied"]),
        _card("beds_in_maintenance", "Beds In Maintenance", beds["maintenance"]),
    ], {}


def _lab(user, today):
    start, end = day_bounds_utc(today)
    entered_today = LabResult.query.filter(LabResult.entered_at >= start, LabResult.entered_at < end)
    return [
        _card("pending_tests", "Pending Tests", _n(LabOrder.query.filter(LabOrder.status.in_(PENDING_LAB)))),
        _card("awaiting_sample", "Awaiting Sample", _n(LabOrder.query.filter_by(status="ordered"))),
        _card("in_processing", "Sample Collected / Processing",
              _n(LabOrder.query.filter(LabOrder.status.in_(("sample_collected", "processing"))))),
        _card("results_entered_today", "Results Entered Today", _n(entered_today)),
        _card("abnormal_today", "Abnormal Results Today", _n(entered_today.filter(LabResult.is_abnormal.is_(True)))),
    ], {}


def _pharmacist(user, today):
    limit = today + timedelta(days=current_app.config["EXPIRY_ALERT_DAYS"])
    stocked = MedicineBatch.query.filter(MedicineBatch.available_quantity > 0)
    return [
        _card("low_stock_medicines", "Low Stock Medicines", len(pharmacy_service.low_stock_medicines())),
        _card("expiring_soon_batches", "Batches Expiring Soon",
              _n(stocked.filter(MedicineBatch.expiry_date >= today, MedicineBatch.expiry_date <= limit))),
        _card("expired_batches_with_stock", "Expired Batches Still In Stock", _n(stocked.filter(MedicineBatch.expiry_date < today))),
        _card("pending_prescriptions", "Prescriptions To Issue",
              _n(Prescription.query.filter(Prescription.status.in_(("pending", "partially_issued"))))),
    ], {}


def _billing(user, today):
    start, end = day_bounds_utc(today)
    open_bills = Bill.query.filter(Bill.status != BILL_PAID)
    outstanding = sum((b.outstanding for b in open_bills.all()), Decimal("0"))
    return [
        _card("today_revenue", "Today's Revenue", _money(_revenue_between(start, end)), "currency"),
        _card("outstanding_amount", "Total Outstanding", _money(outstanding), "currency"),
        _card("unpaid_bills", "Unpaid / Part-Paid Bills", _n(open_bills)),
        _card("bills_generated_today", "Bills Generated Today", _n(Bill.query.filter(Bill.created_at >= start, Bill.created_at < end))),
        _card("payments_today", "Payments Received Today", _n(Payment.query.filter(Payment.paid_at >= start, Payment.paid_at < end))),
    ], {}


_DASHBOARDS = {ROLE_ADMIN: _admin, ROLE_RECEPTIONIST: _receptionist, ROLE_DOCTOR: _doctor, ROLE_NURSE: _nurse,
               ROLE_LAB_TECH: _lab, ROLE_PHARMACIST: _pharmacist, ROLE_BILLING: _billing}


def dashboard_for(user):
    today = local_today()
    cards, extra = _DASHBOARDS[user.role.name](user, today)
    return {"role": user.role.name, "date": today.isoformat(), "generated_at": utc_now_naive().isoformat(),
            "cards": cards, "stats": {c["key"]: c["value"] for c in cards}, **extra}


# ============================================================================
# CHART DATA (Chart.js-ready)
# ============================================================================
COLORS = {"blue": "#3b82f6", "green": "#22c55e", "red": "#ef4444", "orange": "#f97316", "yellow": "#eab308",
          "purple": "#8b5cf6", "grey": "#9ca3af", "teal": "#14b8a6"}
PRIORITY_COLORS = {"critical": COLORS["red"], "high": COLORS["orange"], "medium": COLORS["yellow"], "low": COLORS["green"]}


def _dataset(label, data, color):
    return {"label": label, "data": data, "backgroundColor": color, "borderColor": color}


def _chart(title, chart_type, labels, datasets, **extra):
    return {"title": title, "chart_type": chart_type, "labels": labels, "datasets": datasets, **extra}


def patient_registration_trend(days):
    """New patients per day for the last `days` days (zero-filled so the line has no gaps)."""
    today = local_today()
    first = today - timedelta(days=days - 1)
    start, end = range_bounds_utc(first, today)
    rows = db.session.query(Patient.created_at).filter(Patient.created_at >= start, Patient.created_at < end).all()
    per_day = Counter(to_local_date(r[0]) for r in rows)
    labels = date_range(first, today)
    return _chart(f"Patient registrations - last {days} days", "line", [d.isoformat() for d in labels],
                  [_dataset("New patients", [per_day.get(d, 0) for d in labels], COLORS["blue"])],
                  total=sum(per_day.values()))


def department_wise_patients():
    """Distinct patients per department: seen in an appointment (scheduled/completed) or admitted under a doctor of it."""
    seen = defaultdict(set)
    for dept_id, patient_id in (db.session.query(Appointment.department_id, Appointment.patient_id)
                                .filter(Appointment.status.in_((STATUS_SCHEDULED, STATUS_COMPLETED))).distinct().all()):
        seen[dept_id].add(patient_id)
    for dept_id, patient_id in (db.session.query(Doctor.department_id, Admission.patient_id)
                                .join(Doctor, Doctor.id == Admission.doctor_id).distinct().all()):
        seen[dept_id].add(patient_id)
    depts = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    return _chart("Patients per department", "bar", [d.name for d in depts],
                  [_dataset("Patients", [len(seen[d.id]) for d in depts], COLORS["purple"])])


def bed_occupancy():
    wards = Ward.query.filter_by(is_active=True).order_by(Ward.name).all()
    counts = {w.id: Counter(b.status for b in w.beds) for w in wards}
    overall = _beds_by_status()
    total = sum(overall.values())
    return _chart("Bed occupancy by ward", "bar", [w.name for w in wards], [
        _dataset("Occupied", [counts[w.id]["occupied"] for w in wards], COLORS["red"]),
        _dataset("Available", [counts[w.id]["available"] for w in wards], COLORS["green"]),
        _dataset("Maintenance", [counts[w.id]["maintenance"] for w in wards], COLORS["grey"]),
    ], stacked=True, summary={**overall, "total": total,
                              "occupancy_percent": round(100 * overall["occupied"] / total, 1) if total else 0.0})


def emergency_cases(days):
    """Emergency (triage) cases per day, split by priority."""
    today = local_today()
    first = today - timedelta(days=days - 1)
    start, end = range_bounds_utc(first, today)
    rows = db.session.query(TriageRecord.recorded_at, TriageRecord.priority_level).filter(
        TriageRecord.recorded_at >= start, TriageRecord.recorded_at < end).all()
    per_day = Counter((to_local_date(ts), level) for ts, level in rows)
    labels = date_range(first, today)
    levels = sorted(PRIORITY_RANK, key=PRIORITY_RANK.get, reverse=True)       # critical, high, medium, low
    return _chart(f"Emergency cases - last {days} days", "bar", [d.isoformat() for d in labels],
                  [_dataset(level.title(), [per_day.get((d, level), 0) for d in labels], PRIORITY_COLORS[level])
                   for level in levels], stacked=True, total=len(rows))


def monthly_revenue(months):
    """Billed vs collected money per month (current month last)."""
    first = add_months(month_start(local_today()), -(months - 1))
    last = month_start(local_today())
    end_day = add_months(last, 1) - timedelta(days=1)
    start, end = range_bounds_utc(first, end_day)
    billed, collected = defaultdict(Decimal), defaultdict(Decimal)
    for ts, total in db.session.query(Bill.created_at, Bill.total_amount).filter(Bill.created_at >= start, Bill.created_at < end):
        d = to_local_date(ts)
        billed[(d.year, d.month)] += Decimal(total)
    for ts, amount in db.session.query(Payment.paid_at, Payment.amount).filter(Payment.paid_at >= start, Payment.paid_at < end):
        d = to_local_date(ts)
        collected[(d.year, d.month)] += Decimal(amount)
    keys = [add_months(first, i) for i in range(months)]
    return _chart(f"Monthly revenue - last {months} months", "bar", [f"{k.year}-{k.month:02d}" for k in keys], [
        _dataset("Billed (Rs.)", [_money(billed[(k.year, k.month)]) for k in keys], COLORS["blue"]),
        _dataset("Collected (Rs.)", [_money(collected[(k.year, k.month)]) for k in keys], COLORS["green"]),
    ])


def lab_test_statistics(days):
    """Per test type: how many were ordered and how many results were abnormal."""
    start, end = range_bounds_utc(local_today() - timedelta(days=days - 1), local_today())
    rows = (db.session.query(LabTest.code, LabResult.is_abnormal).select_from(LabOrder)
            .join(LabTest, LabTest.id == LabOrder.lab_test_id)
            .outerjoin(LabResult, LabResult.lab_order_id == LabOrder.id)
            .filter(LabOrder.ordered_at >= start, LabOrder.ordered_at < end).all())
    ordered, abnormal = Counter(), Counter()
    for code, is_abnormal in rows:
        ordered[code] += 1
        abnormal[code] += 1 if is_abnormal else 0
    codes = [c for c, _ in ordered.most_common()]
    return _chart(f"Laboratory tests - last {days} days", "bar", codes, [
        _dataset("Tests ordered", [ordered[c] for c in codes], COLORS["teal"]),
        _dataset("Abnormal results", [abnormal[c] for c in codes], COLORS["red"]),
    ], total=sum(ordered.values()))


def medicine_consumption(days, limit):
    """Most-used medicines: units issued, counted by prescription date."""
    start, end = range_bounds_utc(local_today() - timedelta(days=days - 1), local_today())
    total = db.func.sum(PrescriptionItem.quantity_issued)
    rows = (db.session.query(Medicine.name, total).select_from(PrescriptionItem)
            .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
            .join(Medicine, Medicine.id == PrescriptionItem.medicine_id)
            .filter(Prescription.created_at >= start, Prescription.created_at < end)
            .group_by(Medicine.id, Medicine.name).having(total > 0).order_by(total.desc(), Medicine.name).limit(limit).all())
    return _chart(f"Top {limit} medicines issued - last {days} days", "bar", [r[0] for r in rows],
                  [_dataset("Units issued", [int(r[1]) for r in rows], COLORS["orange"])])
